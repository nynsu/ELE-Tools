# -*- coding: utf-8 -*-
"""
pyRevit Add-in: Lancamento Automatico de Fiacao por Circuito
- Leitura automatica de polos/fases (FNT automatico).
- Busca direta por 'Seção do condutor adotado (mm²)'.
- Fluxo limpo em 2 passos: Circuito e Tipo de Condutor.
"""

from collections import deque
import re
import unicodedata
from Autodesk.Revit.UI.Selection import ObjectType
from pyrevit import revit, DB, forms

doc = revit.doc
uidoc = revit.uidoc

# ==============================================================================
# OPCOES DE CONDUTOR
# ==============================================================================
OPCOES_CABOS = [
    "CABO UNIPOLAR, PVC, 450/750 V",
    "CABO UNIPOLAR, HEPR, 0,6/1 kV",
    "CABO PP CORDPLAST 450/750V 2 CONDUTORES",
    "CABO PP CORDPLAST 450/750V 3 CONDUTORES",
    "CABO SOLAR UNIPOLAR, 1,8 kV",
    "Custom (Digitar manualmente...)"
]

# ==============================================================================
# FUNCOES AUXILIARES
# ==============================================================================
def obter_id_int(elem_id):
    if elem_id is None:
        return -1
    if hasattr(elem_id, "Value"):
        return int(elem_id.Value)
    if hasattr(elem_id, "IntegerValue"):
        return int(elem_id.IntegerValue)
    return int(elem_id)

def extrair_bitola_formatada(texto_bitola):
    if not texto_bitola:
        return "2,5mm²"
    match = re.search(r"(\d+[\.,]?\d*)", str(texto_bitola))
    if match:
        valor = match.group(1).replace(".", ",")
        if "," not in valor:
            valor = valor + ",0"
        return "{}mm²".format(valor)
    return "2,5mm²"

def extrair_valor_parametro(param):
    if not param:
        return ""
    if param.StorageType == DB.StorageType.String:
        txt = param.AsString()
        if txt and txt.strip():
            return txt.strip()
    try:
        val_str = param.AsValueString()
        if val_str and val_str.strip():
            return val_str.strip()
    except Exception:
        pass
    if param.StorageType == DB.StorageType.Double:
        d = param.AsDouble()
        if d > 0:
            return "{:.1f}".format(d).replace(".", ",")
    elif param.StorageType == DB.StorageType.Integer:
        i = param.AsInteger()
        if i > 0:
            return str(i)
    return ""

def obter_bitola_circuito(sistema):
    """Busca com prioridade no parametro oficial do projeto."""
    p = sistema.LookupParameter("Seção do condutor adotado (mm²)")
    if p:
        val = extrair_valor_parametro(p)
        if val:
            return extrair_bitola_formatada(val)

    p_alt = sistema.LookupParameter("Seção do condutor adotado")
    if p_alt:
        val = extrair_valor_parametro(p_alt)
        if val:
            return extrair_bitola_formatada(val)

    param_id = getattr(DB.BuiltInParameter, "RBS_ELEC_CIRCUIT_WIRE_SIZE_PARAM", None)
    if param_id:
        p_wire = sistema.get_Parameter(param_id)
        if p_wire:
            val = extrair_valor_parametro(p_wire)
            if val:
                return extrair_bitola_formatada(val)

    return "2,5mm²"

def obter_condutores_automaticos(sistema):
    """Gera a composicao automatica baseada na quantidade de polos do circuito."""
    polos = 1
    if hasattr(sistema, "Poles"):
        try:
            polos = int(sistema.Poles)
        except Exception:
            polos = 1

    if polos == 1:
        return ["Fase A", "Neutro", "Terra"], "1P (FNT)"
    elif polos == 2:
        return ["Fase A", "Fase B", "Neutro", "Terra"], "2P (2F+N+T)"
    elif polos >= 3:
        return ["Fase A", "Fase B", "Fase C", "Neutro", "Terra"], "3P (3F+N+T)"
    return ["Fase A", "Neutro", "Terra"], "1P (FNT)"

def obter_elementos_conectados(elemento):
    vizinhos = []
    conn_manager = None
    if hasattr(elemento, "ConnectorManager") and elemento.ConnectorManager:
        conn_manager = elemento.ConnectorManager
    elif hasattr(elemento, "MEPModel") and elemento.MEPModel and elemento.MEPModel.ConnectorManager:
        conn_manager = elemento.MEPModel.ConnectorManager

    if not conn_manager:
        return vizinhos

    for conn in conn_manager.Connectors:
        try:
            if not conn.IsConnected:
                continue
        except Exception:
            continue

        try:
            for ref_conn in conn.AllRefs:
                dono = ref_conn.Owner
                if dono and dono.Id != elemento.Id and dono.Id not in [v.Id for v in vizinhos]:
                    vizinhos.append(dono)
        except Exception:
            continue
    return vizinhos

def obter_ponto_elemento(elem):
    if hasattr(elem, "Location") and elem.Location:
        if hasattr(elem.Location, "Point"):
            return elem.Location.Point
        elif hasattr(elem.Location, "Curve"):
            c = elem.Location.Curve
            return (c.GetEndPoint(0) + c.GetEndPoint(1)) * 0.5
    try:
        bbox = elem.get_BoundingBox(None)
        if bbox:
            return (bbox.Min + bbox.Max) * 0.5
    except Exception:
        pass
    return None

def buscar_caminho_bfs(inicio_id, destino_id):
    fila = deque([[inicio_id]])
    visitados = {inicio_id}

    while fila:
        caminho = fila.popleft()
        atual_id = caminho[-1]

        if atual_id == destino_id:
            return caminho

        atual_elem = doc.GetElement(atual_id)
        if not atual_elem:
            continue

        for vizinho in obter_elementos_conectados(atual_elem):
            if vizinho.Id not in visitados:
                visitados.add(vizinho.Id)
                novo_caminho = list(caminho)
                novo_caminho.append(vizinho.Id)
                fila.append(novo_caminho)
    return None

def incrementar_parametro(elem, nome_param, valor=1):
    param = elem.LookupParameter(nome_param)
    if param and not param.IsReadOnly:
        st = param.StorageType
        if st == DB.StorageType.Integer:
            atual = param.AsInteger() or 0
            param.Set(atual + int(valor))
        elif st == DB.StorageType.Double:
            atual = param.AsDouble() or 0.0
            param.Set(atual + float(valor))

def atualizar_tipo_condutor(elem, novo_tipo):
    param = elem.LookupParameter("Tipo de Condutor")
    if param and not param.IsReadOnly:
        atual = param.AsString() or ""
        if not atual:
            param.Set(novo_tipo)
        elif novo_tipo not in atual:
            param.Set("{}; {}".format(atual, novo_tipo))

# ==============================================================================
# EXECUCAO PRINCIPAL
# ==============================================================================
def main():
    cat_quadro_int = int(DB.BuiltInCategory.OST_ElectricalEquipment)
    cat_conduit_int = int(DB.BuiltInCategory.OST_Conduit)

    # 1. Identificacao do Quadro
    quadro = None
    for s_id in uidoc.Selection.GetElementIds():
        elem = doc.GetElement(s_id)
        if elem and elem.Category and obter_id_int(elem.Category.Id) == cat_quadro_int:
            quadro = elem
            break

    if not quadro:
        try:
            ref_quadro = uidoc.Selection.PickObject(
                ObjectType.Element, 
                "Selecione o Quadro de Distribuicao"
            )
            quadro = doc.GetElement(ref_quadro)
        except Exception:
            return

    # 2. Localizacao dos Circuitos
    sistemas = []
    if hasattr(quadro, "MEPModel") and quadro.MEPModel:
        mep = quadro.MEPModel
        if hasattr(mep, "AssignedElectricalSystems") and mep.AssignedElectricalSystems:
            sistemas = list(mep.AssignedElectricalSystems)
        elif hasattr(mep, "ElectricalSystems") and mep.ElectricalSystems:
            sistemas = list(mep.ElectricalSystems)

    if not sistemas:
        coletor = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_ElectricalCircuit).ToElements()
        for circ in coletor:
            be = getattr(circ, "BaseEquipment", None)
            if be and be.Id == quadro.Id:
                sistemas.append(circ)

    if not sistemas:
        forms.alert("Nenhum circuito eletrico encontrado associado a este painel.", title="Quadro sem Circuitos")
        return

    # 3. Montagem da Lista de Circuitos
    opcoes_circuitos = []
    mapa_circuitos = {}

    for sistema in sistemas:
        bitola_formatada = obter_bitola_circuito(sistema)
        condutores_auto, desc_polos = obter_condutores_automaticos(sistema)
        num_circ = sistema.CircuitNumber or "?"
        nome_circ = sistema.LoadName or "Sem Nome"
        cargas = list(sistema.Elements)

        label = "Circ. {} - {} | {} | Bitola: {} ({} carga(s))".format(
            num_circ, nome_circ, desc_polos, bitola_formatada, len(cargas)
        )

        opcoes_circuitos.append(label)
        mapa_circuitos[label] = {
            "circuito": sistema,
            "bitola": bitola_formatada,
            "num_circuito": num_circ,
            "nome_circuito": nome_circ,
            "cargas": cargas,
            "condutores": condutores_auto,
            "desc_polos": desc_polos
        }

    # 4. Passo 1: Escolha do Circuito
    escolha_circ = forms.SelectFromList.show(
        sorted(opcoes_circuitos),
        title="1/2: Selecione o Circuito para Lancar a Fiacao",
        button_name="Avancar",
        multiselect=False
    )
    if not escolha_circ:
        return

    dados_circ = mapa_circuitos[escolha_circ]
    bitola = dados_circ["bitola"]
    cargas = dados_circ["cargas"]
    condutores_finais = dados_circ["condutores"]

    if not cargas:
        forms.alert("O circuito selecionado nao possui cargas conectadas.", title="Aviso")
        return

    # 5. Passo 2: Escolha do Cabo
    escolha_cabo = forms.SelectFromList.show(
        OPCOES_CABOS,
        title="2/2: Selecione o Tipo de Condutor ({})".format(dados_circ["desc_polos"]),
        button_name="Lancar Fiacao",
        multiselect=False
    )
    if not escolha_cabo:
        return

    if "Custom" in escolha_cabo:
        cabo_final = forms.ask_for_string(
            prompt="Digite a descricao do condutor:",
            title="Tipo de Condutor Customizado"
        )
        if not cabo_final:
            return
        cabo_final = cabo_final.strip()
    else:
        cabo_final = escolha_cabo

    forms.toast("Tracando percurso para todas as cargas...", title="Processando")

    filtro_mep = DB.LogicalOrFilter(
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_Conduit),
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_ConduitFitting)
    )
    candidatos_mep = DB.FilteredElementCollector(doc, doc.ActiveView.Id).WherePasses(filtro_mep).ToElements()

    # 6. Rastreamento da Rota
    eletrodutos_circuito_ids = set()
    cargas_atendidas = 0

    for equip in cargas:
        caminho = buscar_caminho_bfs(quadro.Id, equip.Id)

        if not caminho:
            pt_equip = obter_ponto_elemento(equip)
            if pt_equip:
                ordenados = []
                for c in candidatos_mep:
                    pt_c = obter_ponto_elemento(c)
                    if pt_c:
                        dist = pt_equip.DistanceTo(pt_c)
                        if dist <= 3.5:
                            ordenados.append((dist, c))
                ordenados.sort(key=lambda x: x[0])

                for par in ordenados:
                    peca_prox = par[1]
                    caminho_alt = buscar_caminho_bfs(quadro.Id, peca_prox.Id)
                    if caminho_alt:
                        caminho = caminho_alt
                        break

        if caminho:
            cargas_atendidas += 1
            for elem_id in caminho:
                elem = doc.GetElement(elem_id)
                if elem and elem.Category and obter_id_int(elem.Category.Id) == cat_conduit_int:
                    eletrodutos_circuito_ids.add(elem_id)

    if not eletrodutos_circuito_ids:
        forms.alert(
            "Nao foi encontrado trajeto continuo de eletrodutos para as cargas deste circuito.",
            title="Sem Conectividade"
        )
        return

    # 7. Gravacao nos Eletrodutos
    t = DB.Transaction(doc, "Lancar Fiacao por Circuito")
    t.Start()
    try:
        for c_id in eletrodutos_circuito_ids:
            tubo = doc.GetElement(c_id)
            if tubo:
                for cond in condutores_finais:
                    incrementar_parametro(tubo, "{}_{}".format(bitola, cond), 1)
                atualizar_tipo_condutor(tubo, cabo_final)
        t.Commit()
    except Exception as erro_transacao:
        t.RollBack()
        forms.alert("Erro ao gravar dados: {}".format(str(erro_transacao)), title="Falha")
        return

    # 8. Relatorio Final
    forms.alert(
        "Fiação lançada com sucesso! ✅\n\n"
        "• Circuito: {} - {}\n"
        "• Configuração: {}\n"
        "• Bitola aplicada: {}\n"
        "• Condutores lançados: {}\n"
        "• Tipo de Cabo: {}\n"
        "• Cargas alcançadas: {} de {}\n"
        "• Eletrodutos atualizados: {}".format(
            dados_circ["num_circuito"],
            dados_circ["nome_circuito"],
            dados_circ["desc_polos"],
            bitola,
            ", ".join(condutores_finais),
            cabo_final,
            cargas_atendidas,
            len(cargas),
            len(eletrodutos_circuito_ids)
        ),
        title="Concluído"
    )

if __name__ == "__main__":
    main()