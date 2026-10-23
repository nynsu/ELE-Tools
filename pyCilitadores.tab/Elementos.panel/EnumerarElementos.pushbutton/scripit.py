# -*- coding: utf-8 -*-
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *

from pyrevit import revit, forms
import os

doc = revit.doc
uidoc = revit.uidoc

class EnumTagWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        forms.WPFWindow.__init__(self, xaml_file_name)
        
        self.cat_dict = {}
        self.tag_symbols_dict = {}
        
        # Popular Categorias
        categories = doc.Settings.Categories
        for cat in categories:
            if cat.AllowsBoundParameters:
                self.cat_dict[cat.Name] = cat
        
        sorted_cat_names = sorted(self.cat_dict.keys())
        self.CmbCategories.ItemsSource = sorted_cat_names
        if sorted_cat_names:
            self.CmbCategories.SelectedIndex = 0
            
        # Popular Tipos de Tags
        all_symbols = FilteredElementCollector(doc).OfClass(FamilySymbol).ToElements()
        for sym in all_symbols:
            try:
                cat = sym.Category
                if cat and any(k in cat.Name.lower() for k in ["tag", "marca", "identificador"]):
                    tag_name = "{} : {}".format(sym.Family.Name, Element.Name.GetValue(sym))
                    self.tag_symbols_dict[tag_name] = sym
            except:
                pass
                
        sorted_tag_names = sorted(self.tag_symbols_dict.keys())
        self.CmbTags.ItemsSource = sorted_tag_names
        if sorted_tag_names:
            self.CmbTags.SelectedIndex = 0

        self.UpdateParameterList(is_type=True)
        self.result = None

    def ToggleParamType(self, sender, args):
        if hasattr(self, 'CmbParameters'):
            is_type = self.RbTipo.IsChecked
            self.UpdateParameterList(is_type)

    def UpdateParameterList(self, is_type):
        if is_type:
            default_params = ["Marca de tipo", "Comentários de tipo", "Descrição", "Modelo", "Fabricante"]
        else:
            default_params = ["Marca", "Comentários", "Fase de criação", "Fase de demolição"]
        
        self.CmbParameters.ItemsSource = default_params
        self.CmbParameters.Text = default_params[0]

    def ToggleTagPanel(self, sender, args):
        if hasattr(self, 'PanelTag'):
            self.PanelTag.IsEnabled = self.ChkCreateTag.IsChecked

    def OnClickExecutar(self, sender, args):
        self.result = {
            "category_name": self.CmbCategories.SelectedItem,
            "is_type": self.RbTipo.IsChecked,
            "param_name": self.CmbParameters.Text,
            "sufixo": self.TxtSufixo.Text,
            "create_tag": self.ChkCreateTag.IsChecked,
            "tag_symbol": self.tag_symbols_dict.get(self.CmbTags.SelectedItem) if self.ChkCreateTag.IsChecked else None
        }
        self.Close()

def run_script():
    xaml_path = os.path.join(os.path.dirname(__file__), 'ui.xaml')
    window = EnumTagWindow(xaml_path)
    window.ShowDialog()
    
    data = window.result
    if not data or not data["category_name"]:
        return

    cat_name = data["category_name"]
    target_cat = window.cat_dict[cat_name]
    collector = FilteredElementCollector(doc).WherePasses(ElementCategoryFilter(target_cat.Id)).WhereElementIsNotElementType()
    elements_to_process = list(collector)

    if not elements_to_process:
        forms.alert("Nenhum elemento encontrado na categoria selecionada.", exitscript=True)

    param_name = data["param_name"]
    sufixo = data["sufixo"]
    is_type = data["is_type"]
    create_tag = data["create_tag"]
    selected_tag_symbol = data["tag_symbol"]

    with revit.Transaction("Enumerar elementos e taguear"):
        tags_created = 0
        active_view = doc.ActiveView
        error_log = []

        if is_type:
            # CORREÇÃO PARA TIPO: Coleta apenas os TIPOS ÚNICOS para não sobrescrever
            unique_types_map = {}
            for el in elements_to_process:
                elem_type_id = el.GetTypeId()
                if elem_type_id != ElementId.InvalidElementId and elem_type_id not in unique_types_map:
                    # Guarda o primeiro elemento representante e o tipo correspondente
                    unique_types_map[elem_type_id] = (el, doc.GetElement(elem_type_id))

            items_to_loop = list(unique_types_map.values()) # Cada item é uma tupla (representante_instancia, tipo_elemento)
            count = len(items_to_loop)

            for i, (rep_el, target_element) in enumerate(items_to_loop):
                seq_str = str(i + 1)
                value_to_set = "{}{}".format(sufixo, seq_str).strip() if sufixo else seq_str

                param = target_element.LookupParameter(param_name)
                if param and not param.IsReadOnly:
                    param.Set(value_to_set)

                # Se quiser taguear o elemento representante de cada tipo
                if create_tag:
                    try:
                        loc = rep_el.Location
                        point = None
                        if isinstance(loc, LocationPoint):
                            point = loc.Point
                        elif isinstance(loc, LocationCurve):
                            point = loc.Curve.Evaluate(0.5, True)
                        
                        if point:
                            ref = Reference(rep_el)
                            tag = IndependentTag.Create(
                                doc, active_view.Id, ref, False, 
                                TagMode.TM_ADDBY_CATEGORY, TagOrientation.Horizontal, point
                            )
                            if tag and selected_tag_symbol:
                                if not selected_tag_symbol.IsActive:
                                    selected_tag_symbol.Activate()
                                    doc.Regenerate()
                                tag.ChangeTypeId(selected_tag_symbol.Id)
                            if tag:
                                tags_created += 1
                    except Exception as e:
                        if not error_log:
                            error_log.append(str(e))
        else:
            # COMPORTAMENTO NORMAL PARA INSTÂNCIA (Cada porta ganha seu número único)
            count = len(elements_to_process)
            for i, el in enumerate(elements_to_process):
                seq_str = str(i + 1)
                value_to_set = "{}{}".format(sufixo, seq_str).strip() if sufixo else seq_str

                param = el.LookupParameter(param_name)
                if param and not param.IsReadOnly:
                    param.Set(value_to_set)

                if create_tag:
                    try:
                        loc = el.Location
                        point = None
                        if isinstance(loc, LocationPoint):
                            point = loc.Point
                        elif isinstance(loc, LocationCurve):
                            point = loc.Curve.Evaluate(0.5, True)
                        
                        if point:
                            ref = Reference(el)
                            tag = IndependentTag.Create(
                                doc, active_view.Id, ref, False, 
                                TagMode.TM_ADDBY_CATEGORY, TagOrientation.Horizontal, point
                            )
                            if tag and selected_tag_symbol:
                                if not selected_tag_symbol.IsActive:
                                    selected_tag_symbol.Activate()
                                    doc.Regenerate()
                                tag.ChangeTypeId(selected_tag_symbol.Id)
                            if tag:
                                tags_created += 1
                    except Exception as e:
                        if not error_log:
                            error_log.append(str(e))

    msg = "Processo concluído!\nElementos processados: {}\nTags criadas: {}".format(count, tags_created)
    if error_log:
        msg += "\n\nAviso:\n" + error_log[0]
        
    forms.alert(msg, title="Resultado")

if __name__ == "__main__":
    run_script()