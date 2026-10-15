# GitHub: autenticar y publicar

Esta máquina **no está autenticada** en GitHub. Comprobado al construir el repo:

- `git` ✅ instalado (`C:\Program Files\Git\cmd\git.exe`)
- `gh` ❌ **no instalado**
- `git config user.name` / `user.email` ❌ **sin definir**
- Credential helper ❌ **ninguno** — no hay credenciales guardadas

Hay dos caminos. **Opción A** es la más rápida.

---

## Opción A — Token personal (PAT), sin instalar nada

1. Abre <https://github.com/settings/tokens> → **Generate new token (classic)**
2. Marca el alcance **`repo`** (y `workflow` si algún día usas Actions)
3. Copia el token (`ghp_…`) — solo se muestra una vez
4. Configura identidad y remoto:

```powershell
git config --global user.name  "Tu Nombre"
git config --global user.email "tu@email@example.com"

cd "C:\Users\adria\Downloads\Posible Jarvis"
git init
git remote add origin https://github.com/TU_USUARIO/jarvis-kit.git
```

5. Al hacer `push`, Windows **Credential Manager** te pedirá el usuario y la
   contraseña → pega el **token** como contraseña. Queda guardado.

   Si no te lo pide, regístralo de una vez:

```powershell
git config --global credential.helper manager
```

## Opción B — GitHub CLI

```powershell
winget install GitHub.cli
# cerrar y abrir la terminal
gh auth login --web
```

Después publicar es directo:

```powershell
cd "C:\Users\adria\Downloads\Posible Jarvis"
gh repo create jarvis-kit --public --source=. --push
```

---

## Antes del primer push

Comprueba que **no se suben secretos ni rutas de esta máquina**:

```powershell
git status --ignored --short
```

Debe marcar como ignorados:

```
!! jarvis.projects.json     ← rutas absolutas de TU máquina
!! .env                     ← tokens
!! node_modules/
```

`.gitignore` ya los cubre. **Si `jarvis.projects.json` aparece sin `!!`, no hagas
push**: revisa el `.gitignore` primero.

Después:

```powershell
git add -A
git commit -m "jarvis: cerebro unificador v0.1"
git push -u origin main
```

## Verificación final

```powershell
opencode plugin add github:TU_USUARIO/jarvis-kit
opencode plugin list
```

Debe aparecer `github:TU_USUARIO/jarvis-kit`. Y en el navegador,
`https://TU_USUARIO.github.io/jarvis-kit/skills/index.json` debe devolver el
catálogo (tras activar Pages desde `/docs`, ver [INSTALACION.md](INSTALACION.md)).
