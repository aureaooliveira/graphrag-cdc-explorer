# =====================================================================
# setup.ps1
# Prepara o ambiente da PoC e, opcionalmente, roda a indexacao do GraphRAG.
#
# Uso (PowerShell, na raiz do projeto):
#     .\scripts\setup.ps1                 # sobe containers e testa os modelos de nuvem
#     .\scripts\setup.ps1 -Index          # ... e roda a indexacao
#     .\scripts\setup.ps1 -Clean -Index   # apaga output/cache/logs antes de indexar
#     .\scripts\setup.ps1 -Local          # modo 100% local (Ollama), sem custo de API
#
# Observacao: -Clean apaga o cache. Com modelos de nuvem, isso faz a proxima
# indexacao pagar de novo todas as chamadas ao LLM.
# =====================================================================
param(
    [switch]$Local,
    [switch]$Index,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    AVISO: $msg" -ForegroundColor Yellow }

# ---------------------------------------------------------------------
# 1. Arquivo de chaves (data/.env)
# ---------------------------------------------------------------------
if (-not $Local) {
    Write-Step "Verificando data\.env"
    if (-not (Test-Path ".\data\.env")) {
        Copy-Item ".\config\.env.example" ".\data\.env"
        Write-Warn "data\.env criado a partir de config\.env.example. Preencha a chave de API e rode o script de novo."
        exit 1
    }
    Write-Ok "data\.env encontrado"
}

# ---------------------------------------------------------------------
# 2. Containers
# ---------------------------------------------------------------------
Write-Step "Subindo containers"
if ($Local) {
    docker compose --profile local up -d --build
} else {
    docker compose up -d --build
}
if ($LASTEXITCODE -ne 0) { throw "Falha ao subir os containers. O Docker Desktop esta rodando?" }
Write-Ok "Containers no ar"

# ---------------------------------------------------------------------
# 3a. Modo local: baixar modelos no Ollama
# ---------------------------------------------------------------------
if ($Local) {
    Write-Step "Aguardando o Ollama"
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        docker exec ollama ollama list 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "Ollama nao respondeu. Veja 'docker logs ollama'." }

    Write-Step "Baixando modelos (llama3.1:8b e nomic-embed-text)"
    docker exec ollama ollama pull llama3.1:8b
    docker exec ollama ollama pull nomic-embed-text

    Write-Step "Criando llama3.1-8k (contexto de 8192 tokens)"
    docker exec ollama sh -c "printf 'FROM llama3.1:8b\nPARAMETER num_ctx 8192\n' > /tmp/Modelfile"
    docker exec ollama ollama create llama3.1-8k -f /tmp/Modelfile
    Write-Ok "Modelos prontos"

    $settings = Get-Content ".\data\settings.yaml" -Raw
    if ($settings -notmatch "ollama") {
        Write-Warn "data\settings.yaml esta configurado para nuvem. Para o modo local, copie config\settings.ollama.yaml para data\settings.yaml."
    }
}

# ---------------------------------------------------------------------
# 3b. Modo nuvem: testar chave e modelos (custa centavos)
# ---------------------------------------------------------------------
else {
    Write-Step "Testando chave de API e modelos"
    docker exec graphrag python /scripts/test_models.py
    if ($LASTEXITCODE -ne 0) { throw "Teste de modelos falhou. Corrija antes de indexar." }
}

# ---------------------------------------------------------------------
# 4. Limpeza e indexacao
# ---------------------------------------------------------------------
if ($Clean) {
    Write-Step "Apagando output, cache e logs"
    docker exec graphrag rm -rf /data/output /data/cache /data/logs
    Write-Ok "Limpo"
}

if ($Index) {
    Write-Step "Rodando a indexacao (graphrag index)"
    docker exec -it graphrag graphrag index --root /data
    if ($LASTEXITCODE -ne 0) { throw "Indexacao terminou com erro. Veja data\logs\indexing-engine.log." }
    Write-Ok "Indexacao concluida"

    Write-Step "Reiniciando o backend para carregar o novo grafo"
    docker compose restart backend
}

Write-Step "Pronto"
Write-Host "Aplicacao web: http://localhost:5173"
Write-Host 'Consulta:      docker exec -it graphrag graphrag query "O que diz o art. 54-E do CDC?" --root /data --method local'
