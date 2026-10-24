# ELE-Tools (pyRevit Extension)

Extensão personalizada para **Autodesk Revit** desenvolvida para automação de projetos de instalações elétricas através do framework **pyRevit**.

---

## ⚡ Ferramentas Disponíveis

A extensão adiciona a aba **ELE-Tools** e o painel **Utilitários** à barra de ferramentas do Revit, trazendo as seguintes automações:

### 1. 🔌 WireMaster (Lançamento Automático de Fiação)
- **Identificação Inteligente de Circuitos:** Lê as fases, polos e o sistema do circuito para configurar automaticamente a simbologia adequada (Fase, Neutro, Terra, Retorno).
- **Busca de Bitola:** Captura e formata automaticamente a seção dos condutores cadastrada nos parâmetros elétricos (ex: `2,5mm²`, `4,0mm²`).
- **Seleção de Condutores Padronizados:**
  - Cabo Unipolar PVC 450/750V
  - Cabo Unipolar HEPR 0,6/1kV
  - Cabo PP Cordplast (2 ou 3 condutores)
  - Cabo Solar Unipolar 1,8kV
  - Entrada customizada manual
- **Traçado Contínuo em Eletrodutos:** Permite selecionar o circuito e os trechos de eletrodutos interligados para inserir as anotações de fiação em lote.

---

### 2. 📍 ConduitLocator (Locação de Conduítes e Caixas)
- **Cálculo de Cotas e Níveis:** Calcula a altura e distância de tubulações, caixas e eletrodutos em relação à laje/nível informado.
- **Filtro Paramétrico:** Permite definir a altura da laje (em metros) e automatizar cotas ou tags de locação de passagem de eletrodutos.

---

### 3. 💧 PumpSpec (Especificação de Bombas e Motores)
- **Leitura Paramétrica do Equipamento:** Lê parâmetros de tipo e instância de famílias de bombas (vazão, MCA/pressão, potência, tensão e tipo).
- **Padronização da Descrição de Material:** Formata e preenche automaticamente o parâmetro `Descrição do Material` de acordo com os padrões e normas de especificação técnica.

---

### 4. 🔄 Atualizar (Sincronização com o Git com 1 Clique)
- **Atualização Direta no Revit:** Botão integrado com interface visual própria que executa `git pull` para buscar novas atualizações do repositório remoto sem precisar abrir o terminal ou fechar o Revit.
- **Auto-recarga:** Suporta recarregar o pyRevit automaticamente logo após baixar novidades.

---

## 📥 Como Instalar

### Requisitos:
- **Autodesk Revit** (2020 a 2026)
- **pyRevit** instalado ([pyrevitlabs.io](https://pyrevitlabs.io/))
- **Git for Windows** instalado ([git-scm.com](https://git-scm.com/))

### Instalação via Git (Recomendado):
Abra o PowerShell ou Prompt de Comando e execute:

```powershell
cd "$env:APPDATA\pyRevit\Extensions"
git clone https://github.com/nynsu/ELE-Tools.git ELE-Tools.extension
```

### Recarregando no Revit:
1. Abra o Revit.
2. Na aba **pyRevit**, segure a tecla `Shift` e clique em **Reload**.
3. A nova aba **ELE-Tools** aparecerá pronta para uso na sua barra de menus.

---

## 🔄 Como Atualizar

Você pode atualizar a extensão de duas formas:
- **Pelo próprio Revit:** Clique no botão **Utilitários > Atualizar** na aba ELE-Tools.
- **Pelo Terminal:** Navegue até a pasta da extensão e rode `git pull` (ou execute o script `atualizar_git.bat` incluído).

---

## 👨‍💻 Autor

- **ELE-Team** / [@nynsu](https://github.com/nynsu)
