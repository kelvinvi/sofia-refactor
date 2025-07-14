# Sofia Refactor 
**Refatoração de um módulo monolítico de quase 1000 linhas em uma arquitetura Python limpa, legível e escalável.  
O projeto original centralizava toda a lógica da assistente virtual Sofia em um único arquivo `brain.py`.  
Esta versão segmenta responsabilidades, adota boas práticas de engenharia de software e mantém 100% da funcionalidade original.**

## 🔍 Visão Geral

O desafio era: refatorar um único arquivo `brain.py` de quase 1000 linhas em um conjunto de módulos coesos e de responsabilidade única. O resultado da refatoração foi esse:
- **Core**: manutenção de fluxo e roteamento genérico.  
- **Handlers**: lógica específica de domínio (boards, arquivos, geral).  
- **Brain**: ponto de entrada, inicialização de serviços e delegação.

> **Por que assim?**  
> - **Separação de responsabilidades (SRP)**: cada módulo faz uma coisa e faz bem feita.  
> - **Alta coesão, baixo acoplamento**: facilita a manutenção e futura expansão.  

## 📂 Estrutura das Pastas
```text
├── sofia/
│   ├── __init__.py                 # Torna sofia um pacote Python
│   ├── brain.py                    # Entry-point: inicializa serviços, estado, cache e handlers
│   ├── core/                       # Módulos centrais (framework de roteamento)
│   │   ├── __init__.py
│   │   ├── intent_router.py        # Mapeia intents para handlers
│   │   └── responder.py            # Detecta intent e invoca o IntentRouter
│   └── handlers/                   # Lógica de domínio
│       ├── __init__.py
│       ├── boards_handler.py       # Azure Boards: seleção, cache e respostas analíticas
│       ├── file_handler.py         # SharePoint: listagem, busca e formatação de arquivos
│       └── general_handler.py      # Conversas gerais, aprendizado manual e fallback AI
├── requirements.txt                # Dependências Python
└── README.md                       # Documentação 
```
## ⚙️ Guia de Instalação 
### **Clone este repositório em sua máquina:**
```bash
git clone https://github.com/SEU-USER/sofia-refactor.git
cd sofia-refactor
```
### **Crie um ambiente virtual Python:**
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
```

### **Instale as dependências:**
```bash
pip install -r requirements.txt
```

## 📖 Descrição dos Módulos
### **sofia/brain.py**
- Função: Ponto de partida. Cria instâncias de serviços (OpenAI, histórico, SharePoint), estados de usuário e cache, pré-compila regex e inicializa os handlers.

- Decisão: Mantém só a orquestração, delegando toda a lógica a core/ e handlers/.

### **sofia/core/intent_router.py**
- Função: Roteia cada intent detectada para o método correto no contexto (Sofia).

- Por quê? Evita condicionais gigantes em um único lugar e centraliza a “ponte” entre detecção e execução.

### **sofia/core/responder.py**
- Função: Detecta a intent (regex, triggers e pontuação de palavras-chave) e aciona o IntentRouter.

- Por quê? Separa detecção de intenção (parte “inteligente”) do roteamento, respeitando SRP.

### **sofia/handlers/boards_handler.py**
- Função: Tratamento de comandos de Azure Boards — seleção de projeto, cache de DataFrames e análise de consultas (tarefas, estatísticas, visões gerais).

- Decisão: Coesão total em lógica de “boards”; novos comandos podem ser adicionados sem tocar em responder ou router.

### **sofia/handlers/file_handler.py**
- Função: Busca e listagem de arquivos no SharePoint, com múltiplas estratégias (direta, AI, variações, por palavras) e cache.

- Por quê? Agrupa tudo que é “arquivo” num mesmo lugar; código de formatação e validação encapsulado.

### **sofia/handlers/general_handler.py**
- Função: Respostas gerais (cumprimentos, cortesia), fluxo de aprendizado manual e fallback para OpenAI.

- Decisão: Isola casos atípicos e aprendizado do core, mantendo o fluxo principal enxuto.

## 🏗️ Decisões de Design
### **Clean Code & SRP**

- Funções curtas (< 30 linhas), nomes descritivos e comentários apenas onde agregam contexto.

### **PEP 8**

- Imports organizados (stdlib, terceiros, locais), indentação de 4 espaços, linhas ≤ 88 caracteres.

### **Modularização Inteligente**

- core/ para framework de roteamento e detecção; handlers/ para domínios de negócio.

### **Cache Simples**

- Implementado em brain.py como dicionário com timestamps. Mantido genérico para boards e arquivos.

### **Documentação Eficaz**

- Docstrings nos módulos e funções, README.md para visão geral.

### **Escalabilidade & Manutenção**

- Para adicionar um novo domínio basta criar handlers/novo_handler.py e registrá-lo no brain.py.