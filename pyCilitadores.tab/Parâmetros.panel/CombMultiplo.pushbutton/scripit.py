# -*- coding: utf-8 -*-
import os
from pyrevit import revit, DB, forms

doc = revit.doc

class ParamItem(object):
    def __init__(self, param_name, is_type, prefix="", suffix=""):
        self.param_name = param_name
        self.is_type = is_type
        self.prefix = prefix
        self.suffix = suffix

    def __repr__(self):
        type_str = "Tipo" if self.is_type else "Instância"
        p_str = "[{}]".format(self.prefix) if self.prefix else ""
        s_str = "[{}]".format(self.suffix) if self.suffix else ""
        return "{} ({}): {} Parâmetro: {} {}".format(
            self.param_name, type_str, p_str, self.param_name, s_str
        )

def get_safe_name(element):
    if not element:
        return ""
    try:
        name = element.Name
        if name:
            return str(name)
    except:
        pass
    try:
        param = element.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
        if param and param.AsString():
            return param.AsString()
    except:
        pass
    return ""

def get_safe_family_name(elem_type):
    if not elem_type:
        return ""
    try:
        if hasattr(elem_type, 'FamilyName') and elem_type.FamilyName:
            return str(elem_type.FamilyName)
    except:
        pass
    try:
        param = elem_type.get_Parameter(DB.BuiltInParameter.ALL_MODEL_FAMILY_NAME)
        if param and param.AsString():
            return param.AsString()
    except:
        pass
    try:
        if hasattr(elem_type, 'Name') and elem_type.Name:
            return str(elem_type.Name)
    except:
        pass
    return ""

class CondenseParametersWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        super(CondenseParametersWindow, self).__init__(xaml_file_name)
        self.combined_params = []
        self._is_loading = True

        # 1. Carregar Categorias
        self.categories = [
            cat for cat in doc.Settings.Categories 
            if cat.CategoryType == DB.CategoryType.Model and not cat.IsTagCategory
        ]
        self.categories = sorted(self.categories, key=lambda c: c.Name)
        self.cbCategories.ItemsSource = [c.Name for c in self.categories]

        # Seleções padrão
        self.cbFilterLevel.SelectedIndex = 0     # Categoria Inteira
        self.chkOnlyUsed.IsChecked = True        # Padrão: Apenas utilizados
        self.cbInputParamType.SelectedIndex = 0  # Instância
        self.cbTargetType.SelectedIndex = 0      # Instância

        if self.categories:
            self._is_loading = False
            self.cbCategories.SelectedIndex = 0

    def get_category_elements(self):
        selected_cat_name = self.cbCategories.SelectedItem
        if not selected_cat_name:
            return [], None

        target_cat = next((c for c in self.categories if c.Name == selected_cat_name), None)
        if not target_cat:
            return [], None

        collector = DB.FilteredElementCollector(doc)\
                      .OfCategoryId(target_cat.Id)\
                      .WhereElementIsNotElementType()
        elements = list(collector)
        return elements, target_cat

    def OnCategoryChanged(self, sender, e):
        if self._is_loading:
            return
        self.update_filter_options()

    def OnFilterLevelChanged(self, sender, e):
        if self._is_loading:
            return
        self.update_filter_options()

    def OnOnlyUsedChanged(self, sender, e):
        if self._is_loading:
            return
        self.update_filter_options()

    def update_filter_options(self):
        self._is_loading = True
        filter_mode = self.cbFilterLevel.SelectedIndex
        only_used = self.chkOnlyUsed.IsChecked
        elements, target_cat = self.get_category_elements()

        if filter_mode == 0:
            self.lblSelectionList.Text = "3. Todos os elementos da Categoria (Sem filtro extra):"
            self.lstSelectionItems.ItemsSource = ["< Todos os elementos da categoria >"]
            self.lstSelectionItems.SelectAll()
            self.lstSelectionItems.IsEnabled = False

        elif filter_mode == 1:
            self.lblSelectionList.Text = "3. Selecione a(s) Família(s):"
            family_names = set()
            
            if only_used:
                for el in elements:
                    try:
                        elem_type = doc.GetElement(el.GetTypeId())
                        fam_name = get_safe_family_name(elem_type)
                        if fam_name:
                            family_names.add(fam_name)
                    except:
                        pass
            else:
                if target_cat:
                    type_collector = DB.FilteredElementCollector(doc)\
                                       .OfCategoryId(target_cat.Id)\
                                       .WhereElementIsElementType()
                    for t_elem in type_collector:
                        try:
                            fam_name = get_safe_family_name(t_elem)
                            if fam_name:
                                family_names.add(fam_name)
                        except:
                            pass
            
            families = sorted(list(family_names))
            self.lstSelectionItems.ItemsSource = families
            self.lstSelectionItems.IsEnabled = True
            if families:
                self.lstSelectionItems.SelectAll()

        elif filter_mode == 2:
            self.lblSelectionList.Text = "3. Selecione o(s) Tipo(s):"
            type_names = set()
            
            if only_used:
                for el in elements:
                    try:
                        elem_type = doc.GetElement(el.GetTypeId())
                        t_name = get_safe_name(elem_type)
                        if t_name:
                            type_names.add(t_name)
                    except:
                        pass
            else:
                if target_cat:
                    type_collector = DB.FilteredElementCollector(doc)\
                                       .OfCategoryId(target_cat.Id)\
                                       .WhereElementIsElementType()
                    for t_elem in type_collector:
                        t_name = get_safe_name(t_elem)
                        if t_name:
                            type_names.add(t_name)
            
            types = sorted(list(type_names))
            self.lstSelectionItems.ItemsSource = types
            self.lstSelectionItems.IsEnabled = True
            if types:
                self.lstSelectionItems.SelectAll()

        self._is_loading = False
        self.update_input_params()
        self.update_target_params()

    def OnSelectionItemsChanged(self, sender, e):
        if self._is_loading:
            return
        self.update_input_params()
        self.update_target_params()

    def OnInputParamTypeChanged(self, sender, e):
        if self._is_loading:
            return
        self.update_input_params()

    def OnTargetTypeChanged(self, sender, e):
        if self._is_loading:
            return
        self.update_target_params()

    def get_filtered_elements(self):
        elements, _ = self.get_category_elements()
        filter_mode = self.cbFilterLevel.SelectedIndex
        selected_items = list(self.lstSelectionItems.SelectedItems)

        if filter_mode == 0 or not selected_items:
            return elements

        filtered = []
        for el in elements:
            elem_type = doc.GetElement(el.GetTypeId())
            if not elem_type:
                continue

            try:
                if filter_mode == 1:
                    fam_name = get_safe_family_name(elem_type)
                    if fam_name in selected_items:
                        filtered.append(el)
                elif filter_mode == 2:
                    t_name = get_safe_name(elem_type)
                    if t_name in selected_items:
                        filtered.append(el)
            except:
                continue

        return filtered

    def get_sample_element(self):
        elements = self.get_filtered_elements()
        return elements[0] if elements else None, elements

    def is_valid_target_parameter(self, p):
        if not p.Definition:
            return False
            
        if p.StorageType != DB.StorageType.String:
            return False
            
        name_lower = p.Definition.Name.lower()
        
        invalid_target_names = [
            "família", "family", "tipo", "type", "nível", "level",
            "fase construída", "phase created", 
            "fase demolida", "phase demolished", 
            "área", "area", "volume", 
            "comprimento", "length", "perímetro", "perimeter",
            "altura", "height", "largura", "width",
            "espessura", "thickness", "fase", "phase"
        ]
        
        if any(term in name_lower for term in invalid_target_names):
            return False
            
        return True

    def update_input_params(self):
        sample, _ = self.get_sample_element()
        if not sample:
            self.cbInputParam.ItemsSource = []
            return

        is_type = self.cbInputParamType.SelectedIndex == 1
        param_names = set()

        if is_type:
            elem_type = doc.GetElement(sample.GetTypeId())
            if elem_type:
                for p in elem_type.Parameters:
                    if p.Definition:
                        param_names.add(p.Definition.Name)
        else:
            type_id = sample.GetTypeId()
            type_param_ids = set()
            if type_id != DB.ElementId.InvalidElementId:
                elem_type = doc.GetElement(type_id)
                if elem_type:
                    type_param_ids = {p.Id for p in elem_type.Parameters if p.Definition}

            for p in sample.Parameters:
                if p.Definition and p.Id not in type_param_ids:
                    param_names.add(p.Definition.Name)

        self.cbInputParam.ItemsSource = sorted(list(param_names))
        if self.cbInputParam.ItemsSource:
            self.cbInputParam.SelectedIndex = 0

    def update_target_params(self):
        sample, _ = self.get_sample_element()
        if not sample:
            self.cbTargetParam.ItemsSource = []
            return

        is_type = self.cbTargetType.SelectedIndex == 1
        param_names = set()

        if is_type:
            elem_type = doc.GetElement(sample.GetTypeId())
            if elem_type:
                for p in elem_type.Parameters:
                    if p.Definition and not p.IsReadOnly and self.is_valid_target_parameter(p):
                        param_names.add(p.Definition.Name)
        else:
            type_id = sample.GetTypeId()
            type_param_ids = set()
            if type_id != DB.ElementId.InvalidElementId:
                elem_type = doc.GetElement(type_id)
                if elem_type:
                    type_param_ids = {p.Id for p in elem_type.Parameters if p.Definition}

            for p in sample.Parameters:
                if p.Definition and p.Id not in type_param_ids and not p.IsReadOnly and self.is_valid_target_parameter(p):
                    param_names.add(p.Definition.Name)

        self.cbTargetParam.ItemsSource = sorted(list(param_names))
        if self.cbTargetParam.ItemsSource:
            self.cbTargetParam.SelectedIndex = 0

    def AddParamClick(self, sender, e):
        param_name = self.cbInputParam.SelectedItem
        if not param_name:
            forms.alert("Selecione um parâmetro para adicionar.", warn=True)
            return

        is_type = self.cbInputParamType.SelectedIndex == 1
        prefix = self.txtPrefix.Text or ""
        suffix = self.txtSuffix.Text or ""

        item = ParamItem(param_name, is_type, prefix, suffix)
        self.combined_params.append(item)
        
        self.lstSelectedParams.ItemsSource = None
        self.lstSelectedParams.ItemsSource = [str(p) for p in self.combined_params]

        self.txtPrefix.Text = ""
        self.txtSuffix.Text = ""

    def RemoveParamClick(self, sender, e):
        selected_index = self.lstSelectedParams.SelectedIndex
        if selected_index >= 0 and selected_index < len(self.combined_params):
            self.combined_params.pop(selected_index)
            self.lstSelectedParams.ItemsSource = None
            self.lstSelectedParams.ItemsSource = [str(p) for p in self.combined_params]

    def get_parameter_value_as_string(self, holder, param_name):
        if not holder:
            return ""
        param = holder.LookupParameter(param_name)
        if not param:
            return ""

        if param.StorageType == DB.StorageType.String:
            return param.AsString() or ""
        elif param.StorageType == DB.StorageType.Double:
            return str(param.AsValueString() or param.AsDouble())
        elif param.StorageType == DB.StorageType.Integer:
            return str(param.AsInteger())
        elif param.StorageType == DB.StorageType.ElementId:
            val_id = param.AsElementId()
            val_elem = doc.GetElement(val_id)
            return get_safe_name(val_elem) if val_elem else ""
        return ""

    def ExecuteClick(self, sender, e):
        target_param_name = self.cbTargetParam.SelectedItem
        if not target_param_name:
            forms.alert("Selecione o parâmetro de saída.", warn=True)
            return

        if not self.combined_params:
            forms.alert("Adicione pelo menos um parâmetro à combinação.", warn=True)
            return

        elements = self.get_filtered_elements()
        if not elements:
            forms.alert("Nenhum elemento encontrado para a seleção atual.", warn=True)
            return

        is_type_target = self.cbTargetType.SelectedIndex == 1

        with revit.Transaction("Combinação Múltipla de Parâmetros"):
            success_count = 0
            for el in elements:
                elem_type = doc.GetElement(el.GetTypeId())
                
                parts = []
                for item in self.combined_params:
                    holder = elem_type if item.is_type else el
                    val = self.get_parameter_value_as_string(holder, item.param_name)
                    
                    combined_part = "{}{}{}".format(item.prefix, val, item.suffix)
                    parts.append(combined_part)

                final_value = "".join(parts)

                target_holder = elem_type if is_type_target else el
                if target_holder:
                    target_param = target_holder.LookupParameter(target_param_name)
                    if target_param and not target_param.IsReadOnly:
                        target_param.Set(final_value)
                        success_count += 1

        forms.alert("Sucesso! {} elementos atualizados com a combinação.".format(success_count), title="Concluído")
        self.Close()

if __name__ == "__main__":
    xaml_path = os.path.join(os.path.dirname(__file__), "UI.xaml")
    CondenseParametersWindow(xaml_path).ShowDialog()