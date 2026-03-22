# llm 包职责边界

- **做**：OpenAI 兼容 / Anthropic 等协议的请求封装；将 `kernel` 提供的合法动作与观测格式化为模型输入；解析与校验模型输出后再交回 `kernel`。
- **不做**：改写牌山、手牌或绕过 `apply`；不在这里判定和了、番符等。

与 `kernel` 的依赖方向：**llm → kernel**（单向），禁止 `kernel` import `llm`。
