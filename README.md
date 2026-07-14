# VC-Panel

**VC-Panel** is an open-source, self-hosted version control management panel that provides a unified interface for repositories across multiple programming ecosystems, including PHP, Node.js, Python, Java, and .NET.

Built for developers, DevOps engineers, and organizations, VC-Panel simplifies repository administration, deployment workflows, access control, automation, and project collaboration through a modern web interface.

## Features

* Multi-language project support:

  * PHP
  * Node.js
  * Python
  * Java
  * .NET

* Repository management

  * Create, import, archive, and organize repositories
  * Branch and tag visualization
  * Commit history and change tracking

* User and team management

  * Role-based permissions
  * Organization workspaces
  * Repository access policies

* Webhooks and automation

  * CI/CD integration
  * Deployment triggers
  * Custom event handlers

* Self-hosted and extensible

  * Docker support
  * REST API
  * Plugin architecture
  * Open-source under the MIT License

* Developer-focused tools

  * SSH and HTTPS access
  * Release management
  * Issue and milestone integration
  * Activity monitoring and audit logs

## Supported Technology Stacks

| Platform | Status    |
| -------- | --------- |
| PHP      | Supported |
| Node.js  | Supported |
| Python   | Supported |
| Java     | Supported |
| .NET     | Supported |
| Go       | Planned   |
| Rust     | Planned   |

## Why VC-Panel?

Modern teams often work across multiple technology stacks. Managing repositories, deployments, and permissions through different tools creates unnecessary complexity.

VC-Panel provides a single, unified control panel for software projects regardless of language or framework, enabling teams to focus on building products instead of maintaining infrastructure.

## Installation

```bash
git clone https://github.com/your-org/vc-panel.git
cd vc-panel
python install -r requirements.txt
python main.py


## Roadmap

### v1.0

* Repository management
* User authentication
* Team permissions
* Webhooks
* REST API

### v1.5

* Built-in CI pipelines
* Deployment environments
* Plugin marketplace
* Metrics dashboards

### v2.0

* Multi-node clustering
* Distributed storage support
* Enterprise authentication providers
* AI-assisted repository management

## Contributing

Contributions are welcome.

You can help by:

* Reporting bugs
* Improving documentation
* Adding integrations
* Developing plugins
* Reviewing pull requests

Please read `CONTRIBUTING.md` before submitting changes.

## License

MIT License.

VC-Panel is free and open-source software. You are free to use, modify, distribute, and build commercial solutions on top of it.

---

**One panel. Every language. Total control.**


Everything ready. Run these commands in order inside d:\Projects\Python\VC:




---




Step 1 — clean old build

POWERSHELL
Remove-Item -Recurse -Force build\exe.win-amd64-3.13 -ErrorAction SilentlyContinue



Step 2 — rebuild with cx_Freeze

POWERSHELL
.venv\Scripts\python setup_freeze.py build_exe



Step 3 — compile installer (Inno Setup)

POWERSHELL
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss



Step 4 — push to GitHub

POWERSHELL
git push origin main --tags



---




Output will be dist\VC-Setup-0.2.0.exe. Steps 1–3 take ~2–3 minutes total.

