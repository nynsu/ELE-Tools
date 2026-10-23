# -*- coding: utf-8 -*-
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
clr.AddReference('PresentationCore')
clr.AddReference('PresentationFramework')
clr.AddReference('WindowsBase')
clr.AddReference('System')

import os
import System
from System.Windows import Window, Visibility
from System.IO import FileStream, FileMode, FileAccess
from System.Windows.Markup import XamlReader
from Autodesk.Revit.DB import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

class ClearParameterWindow(Window):
    def __init__(self, xaml_path):
        fs = FileStream(xaml_path, FileMode.Open, FileAccess.Read)
        try:
            self.root_window = XamlReader.Load(fs)
        finally:
            fs.Close()
        
        # Referências aos elementos do XAML
        self.cmb_categories = self.root_window.FindName("CmbCategories")
        self.cmb_param = self.root_window.FindName("CmbParam")
        self.chk_is_type = self.root_window.FindName("ChkIsType")
        self.cmb_acao = self.root_window.FindName("CmbAcao")
        self.panel_texto_especifico = self.root_window.FindName("PanelTextoEspecifico")
        self.txt_texto_apagar = self.root_window.FindName("TxtTextoApagar")
        self.txt_filtro = self.root_window.FindName("TxtFiltro")
        
        # Eventos
        self.root_window.FindName("BtnCancelar").Click += self.cancel_click
        self.root_window.FindName("BtnExecutar").Click += self.execute_click
        
        self.cmb_categories.SelectionChanged += self.on_category_changed
        self.chk_is_type.Checked += self.on_type_changed
        self.chk_is_type.Unchecked += self.on_type_changed
        self.cmb_acao.SelectionChanged += self.on_acao_changed

        self.load_categories()

    def load_categories(self):
        cats = doc.Settings.Categories
        cat_list = []
        for cat in cats:
            if cat.AllowsBoundParameters:
                cat_list.append((cat.Name, cat))
        
        cat_list.sort(key=lambda x: x[0])
        
        for name, cat in cat_list:
            item = System.Windows.Controls.ComboBoxItem()
            item.Content = name
            item.Tag = cat
            self.cmb_categories.Items.Add(item)
            
        if self.cmb_categories.Items.Count > 0:
            self.cmb_categories.SelectedIndex = 0

    def on_category_changed(self, sender, e):
        self.update_parameter_list()

    def on_type_changed(self, sender, e):
        self.update_parameter_list()

    def on_acao_changed(self, sender, e):
        if self.cmb_acao.SelectedIndex == 1:
            self.panel_texto_especifico.Visibility = System.Windows.Visibility.Visible
        else:
            self.panel_texto_especifico.Visibility = System.Windows.Visibility.Collapsed

    def get_element_name(self, el):
        if not el:
            return ""
        try:
            return el.Name or ""
        except:
            return ""

    def get_parameters_for_category(self, category, is_type):
        param_names = set()
        
        collector = FilteredElementCollector(doc)\
                    .OfCategoryId(category.Id)\
                    .WhereElementIsNotElementType()\
                    .ToElements()

        for elem in collector:
            target = None
            if is_type:
                type_id = elem.GetTypeId()
                if type_id != ElementId.InvalidElementId:
                    target = doc.GetElement(type_id)
            else:
                target = elem
                
            if target:
                for p in target.Parameters:
                    if p.Definition:
                        if not is_type or p.StorageType == StorageType.String:
                            param_names.add(p.Definition.Name)

        if not param_names:
            binding_map = doc.ParameterBindings
            iterator = binding_map.ForwardIterator()
            iterator.Reset()
            while iterator.MoveNext():
                definition = iterator.Key
                binding = iterator.Current
                if category.Id in binding.Categories:
                    is_type_binding = isinstance(binding, TypeBinding)
                    if is_type_binding == is_type:
                        param_names.add(definition.Name)

        if not param_names:
            symbol_collector = FilteredElementCollector(doc)\
                               .OfCategoryId(category.Id)\
                               .WhereElementIsElementType()\
                               .ToElements()
            for sym in symbol_collector:
                for p in sym.Parameters:
                    if p.Definition:
                        param_names.add(p.Definition.Name)
                break

        return sorted(list(param_names))

    def update_parameter_list(self):
        self.cmb_param.Items.Clear()
        selected_item = self.cmb_categories.SelectedItem
        if not selected_item:
            return

        category = selected_item.Tag
        is_type = self.chk_is_type.IsChecked
        
        params = self.get_parameters_for_category(category, is_type)
        for p_name in params:
            self.cmb_param.Items.Add(p_name)
            
        if self.cmb_param.Items.Count > 0:
            self.cmb_param.SelectedIndex = 0

    def cancel_click(self, sender, e):
        self.root_window.Close()

    def execute_click(self, sender, e):
        selected_item = self.cmb_categories.SelectedItem
        if not selected_item:
            System.Windows.MessageBox.Show("Selecione uma categoria válida.", "Aviso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Warning)
            return

        category = selected_item.Tag
        param_name = self.cmb_param.SelectedItem
        is_type = self.chk_is_type.IsChecked
        acao_index = self.cmb_acao.SelectedIndex
        texto_apagar = self.txt_texto_apagar.Text if acao_index == 1 else ""
        filtro = self.txt_filtro.Text.strip().lower()

        if not param_name:
            System.Windows.MessageBox.Show("Selecione o parâmetro alvo.", "Aviso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Warning)
            return

        if acao_index == 1 and not texto_apagar:
            System.Windows.MessageBox.Show("Digite o texto específico que deseja apagar.", "Aviso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Warning)
            return

        try:
            collector = FilteredElementCollector(doc)\
                        .OfCategoryId(category.Id)\
                        .WhereElementIsNotElementType()\
                        .ToElements()

            count_success = 0
            processed_types = set()

            t = Transaction(doc, "Modificar Parâmetro (pyRevit)")
            t.Start()

            for elem in collector:
                elem_name = self.get_element_name(elem).lower()
                
                if is_type:
                    type_id = elem.GetTypeId()
                    if type_id == ElementId.InvalidElementId:
                        continue
                    if type_id in processed_types:
                        continue
                    
                    target_elem = doc.GetElement(type_id)
                    if not target_elem:
                        continue
                    type_name = self.get_element_name(target_elem).lower()
                    if filtro and filtro not in type_name and filtro not in elem_name:
                        continue
                    processed_types.add(type_id)
                else:
                    target_elem = elem
                    if filtro and filtro not in elem_name:
                        continue

                if not target_elem:
                    continue

                param = target_elem.LookupParameter(str(param_name))
                if param and not param.IsReadOnly:
                    if acao_index == 0:
                        self.clear_parameter_value(param)
                        count_success += 1
                    else:
                        if param.StorageType == StorageType.String:
                            current_val = param.AsString()
                            if current_val:
                                import re
                                pattern = re.compile(re.escape(texto_apagar), re.IGNORECASE)
                                if pattern.search(current_val):
                                    new_val = pattern.sub("", current_val).strip()
                                    param.Set(new_val)
                                    count_success += 1

            t.Commit()

            tipo_inst_str = "Tipos" if is_type else "Elementos"
            msg = "Operação concluída com sucesso!\nForam modificados {} {}.".format(count_success, tipo_inst_str)
            System.Windows.MessageBox.Show(msg, "Sucesso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information)
            self.root_window.Close()

        except Exception as ex:
            if 't' in locals() and t.HasStarted():
                t.RollBack()
            System.Windows.MessageBox.Show("Erro ao executar a rotina:\n{}".format(str(ex)), "Erro", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error)

    def clear_parameter_value(self, param):
        storage_type = param.StorageType
        if storage_type == StorageType.String:
            param.Set("")
        elif storage_type == StorageType.Double:
            param.Set(0.0)
        elif storage_type == StorageType.Integer:
            param.Set(0)
        elif storage_type == StorageType.ElementId:
            param.Set(ElementId.InvalidElementId)

if __name__ == '__main__':
    script_dir = os.path.dirname(__file__)
    xaml_file = os.path.join(script_dir, "UI.xaml")
    
    if os.path.exists(xaml_file):
        window = ClearParameterWindow(xaml_file)
        window.root_window.ShowDialog()
    else:
        print("Ficheiro UI.xaml não encontrado na pasta do script.")