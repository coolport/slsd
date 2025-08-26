## Setup

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh 
```

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 
```

### Clone
```bash
git clone https://github.com/coolport/ssd
cd ssd
```

### Run
```bash
uv sync
uv run lastfm.py
```
