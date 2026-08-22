export function extractPromptVariables(prompt: string) {
  const variables = new Set<string>();
  for (const match of prompt.matchAll(/{{\s*([^{}|]+?)(?:\|[^{}]+)?\s*}}/g)) {
    const name = match[1]?.trim();
    if (name) variables.add(name);
  }
  return [...variables].sort();
}
