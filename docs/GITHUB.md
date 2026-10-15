# GitHub: autenticar y publicar

Estado real de esta máquina tras publicar el repo:

| Componente | Estado |
|---|---|
| `git` | ✅ 2.55.0 (`C:\Program Files\Git\cmd\git.exe`) |
| `gh` (GitHub CLI) | ✅ 2.102.0 — instalado con `winget install GitHub.cli` |
| `gh auth login` | ✅ **Logueado como `FreedomStrik10`** |
| `credential.helper` | ✅ `manager` (Windows Credential Manager) |
| `init.defaultBranch` | ✅ `main` |
| Repo | ✅ `https://github.com/FreedomStrik10/jarvis-kit` (público, rama `main`) |
| GitHub Pages | ✅ activo desde `/docs` → `https://freedomstrik10.github.io/jarvis-kit/` |

---

## Cómo se autenticó

**No se usó ningún token.** Ruta con GitHub CLI:

```powershell
winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
gh auth login --hostname github.com --git-protocol https --web
```

`--web` imprime un código de un solo uso, abre el navegador en
<https://github.com/login/device> y espera a que autorices. **Ninguna credencial
pasa por el historial de comandos.**

---

## Lo que NO funcionó (por si lo intentas otra vez)

### 1. Un PAT *fine-grained* (`github_pat_…`) no crea repositorios

Intenté `POST /user/repos` con un PAT fine-grained → **HTTP 401**. Esas tokens
no pueden crear repos. Además, tienen otra trampa:

> Si el repo **aún no existe**, un fine-grained PAT **no puede darle acceso** —
> solo cubre repos ya seleccionados. El alcance tendría que ser
> **All repositories** y los permisos **Contents: Read and write**.

Y hay más: al probarlo, el token que me pasaron **dejó de valer** en cuestión
de segundos (`Bad credentials` en todo, incluido `/user` que antes funcionaba).
Si vas a generar uno, guárdalo tú y **no lo pegues en ningún chat** —
GitHub revoca tokens expuestos y además queda en el historial.

**Resumen**: para esto, `gh auth login` es mejor que cualquier PAT.

### 2. `git init` creó `master`, no `main`

git 2.55 en Windows sigue por defecto con `master`. Fix:

```powershell
git config --global init.defaultBranch main   # para los próximos repos
git branch -m master main                     # para el actual
git push -u origin main
git push origin --delete master
```

No puedes borrar la rama que es la *por defecto* del repo: primero cambia
`default_branch` con `gh api repos/OWNER/REPO -X PATCH -f default_branch=main`.

---

## Reproducir en otra máquina

```powershell
winget install --id GitHub.cli -e
gh auth login --hostname github.com --git-protocol https --web
git config --global init.defaultBranch main
```

Ya dentro del repo, verificar que no se suben secretos:

```powershell
git status --ignored --short
```

Debe marcar como ignorados `jarvis.projects.json`, `.env` y `node_modules/`.

---

## Referencia

```powershell
gh repo create jarvis-kit --public --source=. --remote=origin --push
gh api repos/FreedomStrik10/jarvis-kit/pages -X POST -f "source[branch]=main" -f "source[path]=/docs"
gh auth status
```
