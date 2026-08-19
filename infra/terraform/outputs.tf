output "vpc_id" {
  value = aws_vpc.main.id
}
output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}
output "database_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = true
}
output "redis_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}
output "alb_dns_name" {
  value = aws_lb.api.dns_name
}
output "bucket_names" {
  value = { for key, bucket in aws_s3_bucket.data : key => bucket.id }
}
output "ecr_repository_urls" {
  value = { for key, repository in aws_ecr_repository.services : key => repository.repository_url }
}
output "secret_arns" {
  value     = { for key, secret in aws_secretsmanager_secret.app : key => secret.arn }
  sensitive = true
}
output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}
output "services_security_group_id" {
  value = aws_security_group.services.id
}
