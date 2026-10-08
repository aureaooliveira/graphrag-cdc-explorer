"""
test_models.py

Teste rápido (custa centavos) para conferir, ANTES da indexação, se a chave
de API e os nomes dos modelos do settings.yaml estão funcionando.

Uso (PowerShell, na pasta do projeto):
    docker exec -it graphrag python /data/test_models.py
"""
import os
import re
import sys

import litellm
import yaml

# Raiz do GraphRAG (onde ficam settings.yaml e .env)
ROOT = os.environ.get("GRAPHRAG_ROOT", "/data")

# Carrega o data/.env (mesmo arquivo que o GraphRAG usa)
env_path = os.path.join(ROOT, ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
else:
    print("AVISO: data/.env não encontrado.")

with open(os.path.join(ROOT, "settings.yaml"), encoding="utf-8") as f:
    cfg = yaml.safe_load(f)


def resolver(valor):
    """Substitui ${VAR} pelo valor da variável de ambiente."""
    if isinstance(valor, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), valor)
    return valor


falhas = 0

try:
    from importlib.metadata import version
    print(f"graphrag {version('graphrag')} | litellm {version('litellm')}\n")
except Exception:  # noqa: BLE001
    pass

# Cada modelo é testado de duas formas:
#   1) chamada simples, como na indexação (o GraphRAG só repassa call_args);
#   2) com a temperature configurada para a busca DRIFT (padrão 0). Modelos
#      de raciocínio costumam aceitar só temperature=1.
drift = cfg.get("drift_search") or {}
temp_drift = drift.get("local_search_temperature", 0)  # padrão do GraphRAG: 0

for nome, m in (cfg.get("completion_models") or {}).items():
    modelo = f"{m['model_provider']}/{m['model']}"
    for rotulo, extra in (("simples", {}), (f"temperature={temp_drift}", {"temperature": temp_drift})):
        try:
            r = litellm.completion(
                model=modelo,
                api_key=resolver(m.get("api_key")),
                messages=[{"role": "user", "content": "Responda apenas: OK"}],
                drop_params=True,  # o GraphRAG também usa drop_params=True
                # mesma regra do GraphRAG: parâmetros da chamada sobrescrevem call_args
                **{**(m.get("call_args") or {}), **extra},
            )
            print(f"[OK]   {nome:<15} {modelo:<28} {rotulo:<14} -> {r.choices[0].message.content!r}")
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"[ERRO] {nome:<15} {modelo:<28} {rotulo:<14} -> {type(e).__name__}: {str(e)[:250]}")

for nome, m in (cfg.get("embedding_models") or {}).items():
    modelo = f"{m['model_provider']}/{m['model']}"
    try:
        r = litellm.embedding(
            model=modelo,
            api_key=resolver(m.get("api_key")),
            input=["Consumidor é toda pessoa física ou jurídica..."],
        )
        dim = len(r.data[0]["embedding"])
        print(f"[OK]   {nome:<22} {modelo:<35} -> vetor de {dim} dimensões")
    except Exception as e:  # noqa: BLE001
        falhas += 1
        print(f"[ERRO] {nome:<22} {modelo:<35} -> {type(e).__name__}: {str(e)[:300]}")

print()
print("Tudo certo, pode indexar." if not falhas else f"{falhas} modelo(s) com erro - corrija antes de indexar.")
sys.exit(1 if falhas else 0)
