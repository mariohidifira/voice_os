terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "${var.environment}-voiceos" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.environment}-voiceos-public-${count.index + 1}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags              = { Name = "${var.environment}-voiceos-private-${count.index + 1}" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  depends_on    = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "alb" {
  name   = "${var.environment}-voiceos-alb"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "services" {
  name   = "${var.environment}-voiceos-services"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port       = 8000
    to_port         = 8081
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "data" {
  name   = "${var.environment}-voiceos-data"
  vpc_id = aws_vpc.main.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.services.id]
  }
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.services.id]
  }
}

resource "aws_kms_key" "data" {
  description             = "VoiceOS ${var.environment} data encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.environment}-voiceos"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "postgres" {
  identifier                  = "${var.environment}-voiceos"
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = var.db_instance_class
  allocated_storage           = 20
  max_allocated_storage       = 100
  db_name                     = "voiceos"
  username                    = "voiceos_admin"
  manage_master_user_password = true
  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [aws_security_group.data.id]
  storage_encrypted           = true
  kms_key_id                  = aws_kms_key.data.arn
  backup_retention_period     = 7
  multi_az                    = var.environment == "prod"
  skip_final_snapshot         = var.environment != "prod"
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.environment}-voiceos"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.environment}-voiceos"
  description                = "VoiceOS cache, queues and pubsub"
  node_type                  = var.redis_node_type
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.data.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  num_cache_clusters         = var.environment == "prod" ? 2 : 1
  automatic_failover_enabled = var.environment == "prod"
}

resource "aws_ecs_cluster" "main" {
  name = "${var.environment}-voiceos"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "services" {
  for_each          = toset(["api", "web", "agent-worker", "worker"])
  name              = "/ecs/${var.environment}-voiceos-${each.key}"
  retention_in_days = 30
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.environment}-voiceos-ecs-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name = "${var.environment}-voiceos-ecs-task"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "ecs_task_data" {
  name = "voiceos-data"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = [for bucket in aws_s3_bucket.data : "${bucket.arn}/*"] },
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [for bucket in aws_s3_bucket.data : bucket.arn] },
      { Effect = "Allow", Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"], Resource = aws_kms_key.data.arn }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_secrets" {
  name = "voiceos-secrets"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue", "kms:Decrypt"], Resource = ["arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.environment}/voiceos/*", aws_kms_key.data.arn] }]
  })
}

resource "aws_ecr_repository" "services" {
  for_each = toset(["api", "web", "agent-worker", "worker"])
  name     = "${var.environment}-voiceos-${each.key}"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "KMS" }
}

locals {
  service_ports     = { api = 8000, web = 3000, agent-worker = 8081, worker = 8082 }
  deployed_services = var.deploy_services ? local.service_ports : {}
  service_commands = {
    agent-worker = ["python", "apps/agent-worker/main.py"]
    worker       = ["python", "apps/worker/main.py"]
  }
  runtime_secrets = [
    { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.app["database"].arn}:DATABASE_URL::" },
    { name = "AUTH_SECRET", valueFrom = "${aws_secretsmanager_secret.app["auth"].arn}:AUTH_SECRET::" },
    { name = "INTERNAL_API_TOKEN", valueFrom = "${aws_secretsmanager_secret.app["internal-api"].arn}:INTERNAL_API_TOKEN::" },
    { name = "LIVEKIT_URL", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:LIVEKIT_URL::" },
    { name = "LIVEKIT_API_KEY", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:LIVEKIT_API_KEY::" },
    { name = "LIVEKIT_API_SECRET", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:LIVEKIT_API_SECRET::" },
    { name = "DEEPGRAM_API_KEY", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:DEEPGRAM_API_KEY::" },
    { name = "ANTHROPIC_API_KEY", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:ANTHROPIC_API_KEY::" },
    { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:OPENAI_API_KEY::" },
    { name = "ELEVENLABS_API_KEY", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:ELEVENLABS_API_KEY::" },
    { name = "RESEND_API_KEY", valueFrom = "${aws_secretsmanager_secret.app["providers"].arn}:RESEND_API_KEY::" }
  ]
}

resource "aws_ecs_task_definition" "services" {
  for_each                 = local.deployed_services
  family                   = "${var.environment}-voiceos-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.key == "agent-worker" ? 1024 : 512
  memory                   = each.key == "agent-worker" ? 2048 : 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([merge({
    name         = each.key
    image        = "${aws_ecr_repository.services[each.key].repository_url}:latest"
    essential    = true
    portMappings = [{ containerPort = each.value, protocol = "tcp" }]
    environment = [
      { name = "APP_ENV", value = var.environment },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "REDIS_URL", value = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0" },
      { name = "S3_BUCKET_RECORDINGS", value = aws_s3_bucket.data["recordings"].id },
      { name = "S3_BUCKET_DOCUMENTS", value = aws_s3_bucket.data["documents"].id },
      { name = "S3_BUCKET_EXPORTS", value = aws_s3_bucket.data["exports"].id },
      { name = "APP_BASE_URL", value = "http://${aws_lb.api.dns_name}" },
      { name = "API_BASE_URL", value = "http://${aws_lb.api.dns_name}" },
      { name = "AUTH_URL", value = "http://${aws_lb.api.dns_name}" },
      { name = "AUTH_TRUST_HOST", value = "true" }
    ]
    secrets          = local.runtime_secrets
    logConfiguration = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.services[each.key].name, awslogs-region = var.aws_region, awslogs-stream-prefix = "ecs" } }
  }, contains(keys(local.service_commands), each.key) ? { command = local.service_commands[each.key] } : {})])
}

resource "aws_s3_bucket" "data" {
  for_each = toset(["recordings", "documents", "exports"])
  bucket   = "${var.environment}-voiceos-${each.key}-${var.account_suffix}"
}

resource "aws_s3_bucket_public_access_block" "data" {
  for_each                = aws_s3_bucket.data
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.data.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_lb" "api" {
  name               = "${var.environment}-voiceos"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "api" {
  name        = "${var.environment}-voiceos-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check { path = "/health" }
}

resource "aws_lb_target_group" "web" {
  name        = "${var.environment}-voiceos-web"
  port        = 3000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id
  health_check { path = "/" }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.api.arn
  priority     = 10
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    path_pattern { values = ["/v1/*", "/internal/*", "/health", "/ready", "/docs*", "/openapi.json"] }
  }
}

resource "aws_ecs_service" "services" {
  for_each        = local.deployed_services
  name            = "${var.environment}-voiceos-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services[each.key].arn
  desired_count   = each.key == "api" ? 2 : 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.services.id]
    assign_public_ip = false
  }
  dynamic "load_balancer" {
    for_each = contains(["api", "web"], each.key) ? [1] : []
    content {
      target_group_arn = each.key == "api" ? aws_lb_target_group.api.arn : aws_lb_target_group.web.arn
      container_name   = each.key
      container_port   = each.value
    }
  }
  depends_on = [aws_lb_listener.api, aws_lb_listener_rule.api]
}

resource "aws_secretsmanager_secret" "app" {
  for_each   = toset(["auth", "providers", "database", "internal-api"])
  name       = "${var.environment}/voiceos/${each.key}"
  kms_key_id = aws_kms_key.data.arn
}
