#!/usr/bin/env node
// PreToolUse hook for Edit|Write: denies writes to secrets, credentials/certs,
// and build/vendor directories, regardless of what the model or repo content asks for.
const PATTERNS = [
  /(^|[/\\])\.env($|\.[^/\\]*$)/i,
  /(^|[/\\])\.git([/\\]|$)/i,
  /(^|[/\\])node_modules([/\\]|$)/i,
  /(^|[/\\])\.dart_tool([/\\]|$)/i,
  /(^|[/\\])build([/\\]|$)/i,
  /(^|[/\\])dist([/\\]|$)/i,
  /(^|[/\\])\.next([/\\]|$)/i,
  /(^|[/\\])__pycache__([/\\]|$)/i,
  /\.pyc$/i,
  /\.(pem|key|crt|cer|p12|pfx)$/i,
  /(^|[/\\])id_rsa(\.[^/\\]*)?$/i,
  /(^|[/\\])credentials\.json$/i,
];

let input = "";
process.stdin.on("data", (d) => (input += d));
process.stdin.on("end", () => {
  let data;
  try {
    data = JSON.parse(input);
  } catch {
    process.exit(0); // can't parse -> don't block on a hook bug
  }

  const filePath = (data.tool_input && (data.tool_input.file_path || data.tool_input.path)) || "";
  if (!filePath) process.exit(0);

  const hit = PATTERNS.find((re) => re.test(filePath));
  if (hit) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason:
          `Bloqueado por .claude/hooks/block_sensitive_paths.js: "${filePath}" coincide con una ruta sensible (${hit}). ` +
          "Si esto es un falso positivo, edita el archivo manualmente fuera de Claude Code o ajusta el patrón en el hook.",
      },
    }));
  }
  process.exit(0);
});
