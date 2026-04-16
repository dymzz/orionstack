# Scripts Usage

`scripts/` 目录当前包含本地开发与最小发布辅助脚本。

## 前置要求

- Windows PowerShell / PowerShell 7
- 已安装 `python`
- 已安装 `npm`
- 已安装 `git`
- 建议在仓库根目录下准备 `.venv`

## 脚本列表

### `dev-backend.ps1`

用途：

- 启动后端开发服务

参数：

- `-AppMode demo|dev|prod`
- `-BackendHost 127.0.0.1`
- `-Port 8000`
- `-CheckOnly`

示例：

```powershell
.\scripts\dev-backend.ps1 -AppMode dev -BackendHost 127.0.0.1 -Port 8000
.\scripts\dev-backend.ps1 -CheckOnly
```

### `dev-frontend.ps1`

用途：

- 启动前端开发服务

参数：

- `-Install`
- `-BackendOrigin http://127.0.0.1:8000`
- `-CheckOnly`

示例：

```powershell
.\scripts\dev-frontend.ps1
.\scripts\dev-frontend.ps1 -Install -BackendOrigin http://127.0.0.1:8000
.\scripts\dev-frontend.ps1 -CheckOnly
```

### `dev-demo.ps1`

用途：

- 一键启动后端与前端开发环境

参数：

- `-AppMode demo|dev|prod`
- `-BackendPort 8000`
- `-BackendReadyTimeoutSeconds 30`
- `-InstallFrontend`
- `-CheckOnly`

示例：

```powershell
.\scripts\dev-demo.ps1
.\scripts\dev-demo.ps1 -AppMode demo -BackendPort 8000 -InstallFrontend
.\scripts\dev-demo.ps1 -CheckOnly
```

### `git-release.ps1`

用途：

- 交互式创建本地版本发布提交
- 同步 `pyproject.toml` 的 `version`
- 创建 git tag
- 推送当前分支与 tag

默认行为：

- tag 格式为 `v<version>`，例如 `v0.1.3`
- `pyproject.toml` 中的 `version` 会被同步为 `0.1.3`
- 若未传 `-Version` 或 `-CommitMessage`，脚本会交互式询问
- 提交前会再做一次确认

参数：

- `-Version 0.1.3`
- `-CommitMessage "feat: ..."`
- `-TagPrefix v`
- `-RemoteName origin`
- `-SkipPush`
- `-CheckOnly`

示例：

```powershell
.\scripts\git-release.ps1
.\scripts\git-release.ps1 -Version 0.1.3 -CommitMessage "feat: complete P7 document management"
.\scripts\git-release.ps1 -Version 0.1.3 -CommitMessage "chore: release 0.1.3" -SkipPush
.\scripts\git-release.ps1 -Version 0.1.3 -CommitMessage "chore: release 0.1.3" -CheckOnly
```

执行结果：

1. 更新 `pyproject.toml` 版本
2. 执行 `git add --all`
3. 执行 `git commit -m "..."`
4. 创建注解 tag：`git tag -a v0.1.3 -m "release v0.1.3"`
5. 推送当前分支与 tag

注意事项：

- 如果 tag 已存在，脚本会直接停止
- 如果当前没有可提交变更，脚本会直接停止
- 如果使用 `-SkipPush`，提交与 tag 只保留在本地
- 如果只想检查参数和版本摘要，可使用 `-CheckOnly`
