# Web：API + 浏览器 UI

仓库总览与安装见根目录 **`README.md`**。

## 结构

- `api/`：FastAPI，内存对局，REST JSON；牌码与内核 `Tile.to_code()` 一致。
- `ui/`：Vite + React + TypeScript，开发期通过代理访问 API。

## 浏览器 UI 进展（当前实现）

### 布局与交互

- **回放式四麻桌面**：上 / 左 / 中 / 右 / 下 分区；中央为场况（场风、局数、本场、供托、余牌、阶段）；四家各含头像占位、自风/庄标记、分数、**分席牌河**（6 列网格）、副露条、门清手牌。
- **视角 `seat`**：下方为「视角座位」；对家在上、下家在右、上家在左（相对视角旋转）。
- **观测模式**：`debug`（默认）四家明牌；`human` 仅自家明牌 + 他家牌背张数（`concealed_count_by_seat`）。
- **打牌**：须打牌阶段仅 **底部（视角 seat）** 手牌可点击高亮张提交 `discard`；其余家操作请用 **合法动作列表**（每条带 `seat`）。
- **鸣牌应答**：`call_response` 时展示说明条；同一巡内依次为 **荣和收集 → 碰杠轮询 → 吃**，非重复 bug。中央显示 `call_response_stage` 与 `call_active_seats`（待操作 seat）。
- **合法动作列表**：API 合并 **四家** 在当面的合法动作（解决仅查视角 seat 时在 `call_response` 下为空的问题）；动作标签含中文（过、荣和、打牌等）。
- **牌图**：`/assets/tiles/` 由 API 挂载；`TileFace` 在图片 404 时回退显示牌 **短码**，避免白块。牌背路径缺省时为 CSS/占位。

### 与 API 的字段约定（观测 JSON 摘要）

除原有 `hand` / `river` / `dora_indicators` 等外，常用扩展包括：

| 字段 | 说明 |
|------|------|
| `hands_by_seat` | debug 下四家门前手牌 `dict[tile_code, count]`；human 为 `null` |
| `melds_by_seat` | 四家副露列表 |
| `last_draw_tile` / `last_draw_seat` | 摸牌提示（用于手牌与摸牌间隔展示） |
| `call_response_stage` / `call_active_seats` | 鸣牌应答子阶段与当前可操作 seat |
| `observe_mode` | 查询参数：`human` \| `debug`，默认 `debug` |

### 参考与素材

- 信息架构曾对照常见「回放/观战」分区做 2D 排布；**不使用第三方游戏贴图**，台布与 UI 为自研样式。

## 依赖

```bash
pip install -e ".[web]"
```

前端依赖见 `ui/package.json`；仓库内已含 `ui/package-lock.json`，安装时用 `npm ci` 可复现锁定版本。

## API 单测

```bash
pip install -e ".[dev,web]"
pytest tests/test_web_api_mvp.py tests/test_legal_actions.py -q
```

## 启动 API

在仓库根目录（`PYTHONPATH` 需包含 `src`，可编辑安装后省略）：

```bash
uvicorn web.api.main:app --reload --host 127.0.0.1 --port 8000
```

## 启动前端

```bash
cd src/web/ui
npm install
npm run dev
```

浏览器打开 Vite 提示的本地地址（默认 `http://localhost:5173`）。`vite.config.ts` 已将 `/api` 与 `/assets` 代理到 `8000` 端口。

## 生产构建（可选）

```bash
cd src/web/ui
npm run build
```

可将 `ui/dist` 交由任意静态服务器托管，并配置反向代理到 API。
