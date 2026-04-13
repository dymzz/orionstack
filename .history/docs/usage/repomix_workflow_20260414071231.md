# Repomix 与双仓同步使用说明

## 1. 文档目标

本文档说明主工程仓中 Repomix 相关脚本的用途、调用方式、输出文件及推荐使用场景。

当前相关脚本包括：

- `scripts/build-repomix.ps1`
- `scripts/kb.ps1`
- `scripts/start-kb-sync.ps1`

---

## 2. 脚本职责

### 2.1 `build-repomix.ps1`
用于生成 Repomix 输出文件。

支持两类输出：

1. 主工程全量输出
   - `repomix-output.xml`
   - `repomix-output.md`

2. 文档归一化输出
   - `repomix-docs.md`

### 2.2 `kb.ps1`
作为双仓同步的薄入口脚本使用。

### 2.3 `start-kb-sync.ps1`
作为双仓同步的流程控制脚本使用。

---

## 3. 常用命令

### 3.1 生成主工程全量 Repomix

```powershell
.\scripts\build-repomix.ps1