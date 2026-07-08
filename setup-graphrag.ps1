# =====================================================================
# setup-graphrag.ps1
# Automatiza: subir containers, baixar modelos, criar modelo com
# contexto ampliado, e rodar a indexacao do GraphRAG.
#
# Uso: abra o PowerShell na pasta do projeto (onde esta o
# docker-compose.yml) e rode:
#     .\setup-graphrag.ps1
#
# Ao final, o container "graphrag" fica rodando e pronto para
# voce entrar com "docker exec -it graphrag bash" e fazer queries.
# =====================================================================

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}

function Write-Warn($msg) {
    Write-Host "    AVISO: $msg" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------
# 1. Subir os containers
# ---------------------------------------------------------------------
Write-Step "Subindo containers (ollama + graphrag)"
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao subir os containers. Verifique se o Docker Desktop esta rodando."
}
Write-Ok "Containers no ar"

# ---------------------------------------------------------------------
# 2. Esperar o Ollama responder antes de continuar
# ---------------------------------------------------------------------
Write-Step "Aguardando o servico do Ollama ficar pronto"
$maxTries = 30
$ready = $false
for ($i = 1; $i -le $maxTries; $i++) {
    try {
        docker exec ollama ollama list | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
    } catch {}
    Write-Host "    tentativa $i/$maxTries..."
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    throw "Ollama nao respondeu a tempo. Rode 'docker logs ollama' para investigar."
}
Write-Ok "Ollama pronto"

# ---------------------------------------------------------------------
# 3. Baixar os modelos (LLM + embedding)
# ---------------------------------------------------------------------
Write-Step "Baixando modelo de linguagem (llama3.1:8b) - pode demorar alguns minutos"
docker exec ollama ollama pull llama3.1:8b
Write-Ok "llama3.1:8b baixado"

Write-Step "Baixando modelo de embedding (nomic-embed-text)"
docker exec ollama ollama pull nomic-embed-text
Write-Ok "nomic-embed-text baixado"

# ---------------------------------------------------------------------
# 4. Criar variante do modelo com contexto ampliado (num_ctx 8192)
# ---------------------------------------------------------------------
Write-Step "Criando modelo llama3.1-8k com contexto ampliado"
docker exec ollama sh -c "printf 'FROM llama3.1:8b\nPARAMETER num_ctx 8192\n' > /tmp/Modelfile"
docker exec ollama ollama create llama3.1-8k -f /tmp/Modelfile
Write-Ok "llama3.1-8k criado"

Write-Host ""
docker exec ollama ollama list

# ---------------------------------------------------------------------
# 5. Checar se o settings.yaml esta apontando para o modelo certo
# ---------------------------------------------------------------------
Write-Step "Verificando settings.yaml"
$settingsPath = ".\data\settings.yaml"
if (Test-Path $settingsPath) {
    $content = Get-Content $settingsPath -Raw
    if ($content -notmatch "llama3.1-8k") {
        Write-Warn "settings.yaml nao referencia 'llama3.1-8k'. Confirme se o campo 'model' em completion_models aponta para esse nome."
    }
    if ($content -notmatch "http://ollama:11434") {
        Write-Warn "settings.yaml nao usa 'http://ollama:11434' como api_base. Dentro do container, o Ollama deve ser acessado pelo nome do servico, nao 'localhost'."
    }
} else {
    Write-Warn "Nao encontrei .\data\settings.yaml. Confirme o caminho antes de continuar."
}

# ---------------------------------------------------------------------
# 6. Rodar a indexacao dentro do container graphrag
# ---------------------------------------------------------------------
Write-Step "Rodando graphrag index dentro do container (isso pode demorar bastante sem GPU)"
docker exec -it graphrag graphrag index --root /data
if ($LASTEXITCODE -ne 0) {
    Write-Warn "A indexacao terminou com erro. Revise os logs acima antes de fazer queries."
} else {
    Write-Ok "Indexacao concluida com sucesso"
}

# ---------------------------------------------------------------------
# 7. Pronto
# ---------------------------------------------------------------------
Write-Step "Tudo pronto!"
Write-Host "Para fazer suas queries, entre no container com:"
Write-Host ""
Write-Host "    docker exec -it graphrag bash" -ForegroundColor White
Write-Host ""
Write-Host "E depois use, por exemplo:"
Write-Host ""
Write-Host '    graphrag query --root /data --method local --query "o que diz o artigo 1 do CDC?"' -ForegroundColor White
Write-Host '    graphrag query --root /data --method global --query "quais sao os principais direitos do consumidor?"' -ForegroundColor White
Write-Host ""