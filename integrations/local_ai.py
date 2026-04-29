import subprocess
import json
import re
import textwrap
import requests
from requests.exceptions import ConnectionError, Timeout

OLLAMA_CONFIG = {
    "model": "phi4-mini:3.8b",
    "api_endpoint": "http://127.0.0.1:11434/api/generate",
    "ollama_host": "http://127.0.0.1:11434"
}

def verificar_conexao_ollama() -> str:
    """Verifica se o servidor do Ollama está acessível."""
    try:
        response = requests.get(OLLAMA_CONFIG["ollama_host"], timeout=5)
        response.raise_for_status()
        return ""
    except (ConnectionError, Timeout):
        return (
            "ERRO_OLLAMA_OFFLINE: Não foi possível conectar ao Ollama. "
            "Para usar a análise por IA, certifique-se de que o Ollama "
            "está instalado, em execução e acessível em "
            f"{OLLAMA_CONFIG['ollama_host']}."
        )
    except Exception as e:
        return (
            f"ERRO_INESPERADO_CONEXAO_OLLAMA: Ocorreu um erro inesperado ao "
            f"tentar conectar ao Ollama: {e}"
        )

def chamar_llm_ollama(prompt: str) -> str:
    """Envia um prompt para a API do Ollama e retorna a resposta."""
    
    erro_conexao = verificar_conexao_ollama()
    if erro_conexao:
        return erro_conexao

    try:
        model_name = OLLAMA_CONFIG["model"]
        result = subprocess.run(
            ["ollama", "run", model_name],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1800
        )
        
        if result.returncode != 0:
            stderr_output = result.stderr.decode("utf-8", errors="ignore").strip()
            return f"ERRO_OLLAMA_CLI: O comando 'ollama run {model_name}' falhou. Código de saída: {result.returncode}. Erro: {stderr_output}"

        saida = result.stdout.decode("utf-8", errors="ignore").strip()
        return saida
        
    except FileNotFoundError:
        return "ERRO_OLLAMA_CLI: O comando 'ollama' não foi encontrado. Verifique se o Ollama está instalado e no PATH do sistema."
    except subprocess.TimeoutExpired:
        return f"ERRO_OLLAMA_CLI: O comando 'ollama run {model_name}' excedeu o tempo limite de 1800 segundos."
    except Exception as e:
        return f"ERRO_INESPERADO_CLI: {e}"

def extrair_inteligencia_local(texto: str) -> dict:
    """
    Solicita a extração estruturada de dados à LLM Local, 
    separando a análise textual do JSON.
    Retorna um dicionário com 'json_data', 'text_analysis', e 'erro'.
    """
    prompt = textwrap.dedent(f"""
    Você é um robô de extração de dados. Sua única tarefa é preencher o modelo JSON abaixo com informações do texto fornecido.

    REGRAS:
    - Retorne APENAS o código JSON. NENHUM outro texto é permitido.
    - Siga EXATAMENTE a estrutura do "ESTRUTURA JSON EXIGIDA". Não invente campos.
    - Preencha os campos usando apenas informações do texto.
    - Se a informação não existir, use `null` ou `[]`.

    ESTRUTURA JSON EXIGIDA:
    ```json
    {{
      "identificacao_banco": "string (ex: CAIXA, SANTANDER, ITAU, N/A)",
      "resumo_movimentacao": {{"periodo": "string", "total_credito": "string", "total_debito": "string", "quantidade_transacoes": "número inteiro"}},
      "perfil_cliente": {{"nome": "string", "cpf_cnpj": "string", "atividade_profissional": "string", "renda_mensal_informada": "string", "capital_social": "string", "faturamento_anual": "string", "pep": "sim/não/relacionado", "midia_negativa": "sim/não + breve descrição"}},
      "principais_contrapartes": [{{"nome": "string", "documento": "string", "valor_total": "string", "tipo": "REMETENTE/DESTINATÁRIO", "meio": "PIX/TED/ETC"}}],
      "analise_risco": {{"suspeitas_pld": ["lista de frases curtas como 'Fracionamento', 'Incompatibilidade', 'Conta de Passagem'"], "bandeiras_vermelhas": ["alertas de comportamento atípico"], "vinculos_identificados": ["relações societárias ou familiares descritas"]}},
      "conclusao_ia": "breve resumo técnico da materialidade encontrada"
    }}
    ```

    Agora, preencha a estrutura JSON acima usando o seguinte texto. Retorne apenas o JSON.

    TEXTO PARA ANÁLISE:
    {texto}
    """)
    
    resposta = chamar_llm_ollama(prompt)
    
    resultado = {
        "json_data": None,
        "text_analysis": None,
        "erro": None
    }

    if resposta.startswith("ERRO_"):
        resultado["erro"] = resposta
        return resultado

    try:
        match = re.search(r'\{.*\}', resposta, re.DOTALL)
        
        if match:
            json_str = match.group(0)
            text_analysis = resposta.replace(json_str, "").strip()
            if text_analysis:
                resultado["text_analysis"] = text_analysis
            
            try:
                resultado["json_data"] = json.loads(json_str)
            except json.JSONDecodeError:
                resultado["erro"] = f"Falha ao decodificar o bloco JSON encontrado. A resposta completa da IA foi preservada na análise textual para depuração."
                resultado["text_analysis"] = resposta
        else:
            resultado["erro"] = "Nenhum bloco JSON válido foi retornado pela IA."
            resultado["text_analysis"] = resposta

    except Exception as e:
        resultado["erro"] = f"Erro inesperado ao processar a resposta da IA: {e}"
        resultado["text_analysis"] = resposta

    return resultado