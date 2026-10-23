# -*- coding: utf-8 -*-
import os
import System
from pyrevit import revit, DB, forms

doc = revit.doc

class AdvancedParameterUpdaterWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        super(AdvancedParameterUpdaterWindow, self).__init__(xaml_file_name)
        
        # 1. Carregar Categorias de Modelo
        self.categories = [
            cat for cat in doc.Settings.Categories 
            if cat.CategoryType == DB.CategoryType.Model and not cat.IsTagCategory
        ]
        self.categories = sorted(self.categories, key=lambda c: c.Name)
        
        self.cbCategories.ItemsSource = [c.Name for c in self.categories]
        if self.categories:
            self.cbCategories.SelectedIndex = 0

        # Seleções padrão para Tipo/Instância
        self.cbOriginType.SelectedIndex = 0 # Instância
        self.cbTargetType.SelectedIndex = 0 # Instância

        # Configurar eventos para alternância de modo
        if hasattr(self, 'rbCopyMode') and hasattr(self, 'rbTextMode'):
            self.rbCopyMode.Checked += self.on_mode_changed
            self.rbTextMode.Checked += self.on_mode_changed
            self.rbCopyMode.IsChecked = True # Inicia no modo cópia por padrão

    def on_mode_changed(self, sender, e):
        """Alterna a visibilidade entre copiar parâmetro ou digitar texto livre."""
        is_copy_mode = self.rbCopyMode.IsChecked
        if hasattr(self, 'pnlCopySource'):
            self.pnlCopySource.Visibility = System.Windows.Visibility.Visible if is_copy_mode else System.Windows.Visibility.Collapsed
        if hasattr(self, 'pnlTextSource'):
            self.pnlTextSource.Visibility = System.Windows.Visibility.Visible if not is_copy_mode else System.Windows.Visibility.Collapsed

    def OnCategoryChanged(self, sender, e):
        self.update_origin_parameters()

    def OnOriginTypeChanged(self, sender, e):
        self.update_origin_parameters()

    def OnOriginParamChanged(self, sender, e):
        self.update_target_parameters()

    def OnTargetTypeChanged(self, sender, e):
        self.update_target_parameters()

    def get_elements_and_sample(self):
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
        sample = elements[0] if elements else None
        return elements, sample

    def is_yes_no_parameter(self, p):
        """Identifica se o parâmetro é do tipo Sim/Não (Booleano)."""
        if not p or not p.Definition:
            return False
        try:
            if hasattr(p.Definition, "GetDataType") and p.Definition.GetDataType() == DB.SpecTypeId.Boolean.YesNo:
                return True
        except:
            pass
        try:
            if hasattr(p.Definition, "ParameterType") and p.Definition.ParameterType == DB.ParameterType.YesNo:
                return True
        except:
            pass
        return False

    def is_system_or_restricted_parameter(self, p):
        """Filtro rigoroso contra parâmetros de sistema, fases, tipos, famílias e metadados."""
        if not p.Definition:
            return True

        name_lower = p.Definition.Name.lower()
        
        restricted_terms = [
            "família", "family", "tipo", "type", "nível", "level",
            "fase construída", "phase created", "fase demolida", "phase demolished", 
            "fase", "phase", "comprimento", "length", "área", "area", "volume",
            "custo", "cost"
        ]
        
        if any(term in name_lower for term in restricted_terms):
            return True

        return False

    def is_valid_target_parameter(self, p, input_storage_type):
        """Filtra a SAÍDA: bloqueia somente leitura, booleanos e parâmetros de sistema restritos."""
        if not p.Definition or p.IsReadOnly:
            return False
            
        if self.is_yes_no_parameter(p):
            return False
            
        if self.is_system_or_restricted_parameter(p):
            return False

        if input_storage_type in [DB.StorageType.Double, DB.StorageType.Integer]:
            allowed_storage = [DB.StorageType.String, DB.StorageType.Double, DB.StorageType.Integer]
        else:
            allowed_storage = [DB.StorageType.String]

        return p.StorageType in allowed_storage

    def update_origin_parameters(self):
        elements, sample = self.get_elements_and_sample()
        if not sample:
            self.cbOriginParam.ItemsSource = []
            return

        is_type_origin = self.cbOriginType.SelectedIndex == 1 
        elem_type = doc.GetElement(sample.GetTypeId()) if sample else None

        params = []
        holder = elem_type if is_type_origin else sample
        if holder:
            for p in holder.Parameters:
                if p.Definition and not self.is_yes_no_parameter(p):
                    params.append(p.Definition.Name)

        self.cbOriginParam.ItemsSource = sorted(list(set(params)))
        if self.cbOriginParam.ItemsSource:
            self.cbOriginParam.SelectedIndex = 0
        
        self.update_target_parameters()

    def update_target_parameters(self):
        elements, sample = self.get_elements_and_sample()
        if not sample:
            self.cbTargetParam.ItemsSource = []
            return

        is_copy_mode = True
        if hasattr(self, 'rbCopyMode'):
            is_copy_mode = self.rbCopyMode.IsChecked

        origin_param_name = self.cbOriginParam.SelectedItem
        is_type_origin = self.cbOriginType.SelectedIndex == 1
        elem_type = doc.GetElement(sample.GetTypeId()) if sample else None
        
        input_storage_type = DB.StorageType.String 
        if is_copy_mode and origin_param_name:
            origin_holder = elem_type if is_type_origin else sample
            if origin_holder:
                op = origin_holder.LookupParameter(origin_param_name)
                if op:
                    input_storage_type = op.StorageType
        elif not is_copy_mode:
            input_storage_type = DB.StorageType.String

        is_type_target = self.cbTargetType.SelectedIndex == 1 
        param_names = []

        target_holder_sample = elem_type if is_type_target else sample
        if target_holder_sample:
            type_id = sample.GetTypeId()
            type_param_ids = set()
            if not is_type_target and type_id != DB.ElementId.InvalidElementId:
                et = doc.GetElement(type_id)
                if et:
                    type_param_ids = {p.Id for p in et.Parameters if p.Definition}

            for p in target_holder_sample.Parameters:
                if p.Definition:
                    if not is_type_target and p.Id in type_param_ids:
                        continue
                    if is_copy_mode:
                        valid = self.is_valid_target_parameter(p, input_storage_type)
                    else:
                        valid = (p.StorageType == DB.StorageType.String and not p.IsReadOnly and not self.is_system_or_restricted_parameter(p))
                    
                    if valid:
                        param_names.append(p.Definition.Name)

        self.cbTargetParam.ItemsSource = sorted(list(set(param_names)))
        if self.cbTargetParam.ItemsSource:
            self.cbTargetParam.SelectedIndex = 0

    def cancel_click(self, sender, e):
        """Fecha a janela ao clicar em Cancelar."""
        self.Close()

    def ExecuteClick(self, sender, e):
        selected_cat_name = self.cbCategories.SelectedItem
        target_param_name = self.cbTargetParam.SelectedItem
        is_type_target = self.cbTargetType.SelectedIndex == 1

        is_copy_mode = True
        if hasattr(self, 'rbCopyMode'):
            is_copy_mode = self.rbCopyMode.IsChecked

        if not selected_cat_name or not target_param_name:
            forms.alert("Por favor, preencha a categoria e o parâmetro de destino.")
            return

        origin_param_name = self.cbOriginParam.SelectedItem if is_copy_mode else None
        is_type_origin = self.cbOriginType.SelectedIndex == 1 if is_copy_mode else False
        
        custom_text = ""
        if not is_copy_mode and hasattr(self, 'txtCustomText'):
            custom_text = self.txtCustomText.Text or ""

        if is_copy_mode and not origin_param_name:
            forms.alert("Selecione o parâmetro de origem.")
            return

        elements, _ = self.get_elements_and_sample()

        with revit.Transaction("Atualizar Parâmetros em Lote"):
            success_count = 0
            for el in elements:
                elem_type = doc.GetElement(el.GetTypeId())
                
                target_holder = elem_type if is_type_target else el
                if not target_holder:
                    continue

                target_param = target_holder.LookupParameter(target_param_name)
                if not target_param or target_param.IsReadOnly:
                    continue

                # MODO 1: Copiar de outro parâmetro
                if is_copy_mode:
                    source_holder = elem_type if is_type_origin else el
                    if not source_holder:
                        continue
                    
                    source_param = source_holder.LookupParameter(origin_param_name)
                    if not source_param:
                        continue

                    if target_param.StorageType == DB.StorageType.String:
                        val = ""
                        if source_param.StorageType == DB.StorageType.String:
                            val = source_param.AsString() or ""
                        elif source_param.StorageType == DB.StorageType.Double:
                            val = str(source_param.AsValueString() or source_param.AsDouble())
                        elif source_param.StorageType == DB.StorageType.Integer:
                            val = str(source_param.AsInteger())
                        elif source_param.StorageType == DB.StorageType.ElementId:
                            val_id = source_param.AsElementId()
                            val_elem = doc.GetElement(val_id)
                            val = val_elem.Name if val_elem else ""
                        
                        target_param.Set(val)
                        success_count += 1

                    elif target_param.StorageType == DB.StorageType.Double:
                        if source_param.StorageType == DB.StorageType.Double:
                            target_param.Set(source_param.AsDouble())
                            success_count += 1
                        elif source_param.StorageType == DB.StorageType.Integer:
                            target_param.Set(float(source_param.AsInteger()))
                            success_count += 1

                    elif target_param.StorageType == DB.StorageType.Integer:
                        if source_param.StorageType == DB.StorageType.Integer:
                            target_param.Set(source_param.AsInteger())
                            success_count += 1
                        elif source_param.StorageType == DB.StorageType.Double:
                            target_param.Set(int(source_param.AsDouble()))
                            success_count += 1

                # MODO 2: Escrever texto fixo / customizado
                else:
                    if target_param.StorageType == DB.StorageType.String:
                        target_param.Set(custom_text)
                        success_count += 1

        forms.alert("Processo concluído! {} elementos atualizados com sucesso.".format(success_count), title="Sucesso")
        self.Close()

if __name__ == "__main__":
    xaml_path = os.path.join(os.path.dirname(__file__), "UI.xaml")
    AdvancedParameterUpdaterWindow(xaml_path).ShowDialog()