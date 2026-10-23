# -*- coding: utf-8 -*-
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
clr.AddReference('PresentationCore')
clr.AddReference('PresentationFramework')
clr.AddReference('WindowsBase')
clr.AddReference('System')
clr.AddReference('System.Windows.Forms')

import os
import System
from System.Windows import Window
from System.IO import FileStream, FileMode, FileAccess
from System.Windows.Markup import XamlReader
from System.Windows.Forms import SaveFileDialog, DialogResult
from Autodesk.Revit.DB import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

class ExportWindow(Window):
    def __init__(self, xaml_path):
        fs = FileStream(xaml_path, FileMode.Open, FileAccess.Read)
        try:
            self.root_window = XamlReader.Load(fs)
        finally:
            fs.Close()
        
        # Referências aos elementos do XAML
        self.cmb_categories = self.root_window.FindName("CmbCategories")
        self.txt_filtro = self.root_window.FindName("TxtFiltro")
        self.chk_tag = self.root_window.FindName("ChkTag")
        self.txt_sufixo = self.root_window.FindName("TxtSufixo")
        self.txt_excel_path = self.root_window.FindName("TxtExcelPath")
        
        # Atribuindo os eventos programaticamente
        self.root_window.FindName("BtnBrowse").Click += self.browse_click
        self.root_window.FindName("BtnCancelar").Click += self.cancel_click
        self.root_window.FindName("BtnExportar").Click += self.export_click
        
        self.load_categories()

    def load_categories(self):
        self.cmb_categories.Items.Add("ViewSchedule (Tabelas de Quantidades)")
        self.cmb_categories.SelectedIndex = 0

    def browse_click(self, sender, e):
        dialog = SaveFileDialog()
        dialog.Filter = "Ficheiro Excel (*.xlsx)|*.xlsx|Todos os ficheiros (*.*)|*.*"
        dialog.Title = "Selecionar ficheiro Excel (.xlsx) principal"
        
        if dialog.ShowDialog() == DialogResult.OK:
            self.txt_excel_path.Text = dialog.FileName

    def cancel_click(self, sender, e):
        self.root_window.Close()

    def export_click(self, sender, e):
        file_path = self.txt_excel_path.Text
        filtro_nome = self.txt_filtro.Text
        sufixo = self.txt_sufixo.Text

        if not file_path:
            System.Windows.MessageBox.Show("Por favor, selecione um ficheiro Excel (.xlsx) de destino.", "Aviso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Warning)
            return

        try:
            # Coleta todas as tabelas (ViewSchedule) do projeto
            schedules = FilteredElementCollector(doc)\
                        .OfClass(ViewSchedule)\
                        .WhereElementIsNotElementType()\
                        .ToElements()

            out_data = []
            out_names = []

            for sched in schedules:
                if not sched.IsTemplate and filtro_nome.lower() in sched.Name.lower():
                    section_data = sched.GetTableData().GetSectionData(SectionType.Body)
                    if not section_data:
                        continue
                    
                    n_rows = section_data.NumberOfRows
                    n_cols = section_data.NumberOfColumns
                    
                    sched_rows = []
                    has_actual_content = False
                    
                    for r in range(n_rows):
                        row_data = []
                        row_has_value = False
                        for c in range(n_cols):
                            val = sched.GetCellText(SectionType.Body, r, c)
                            row_data.append(val if val is not None else "")
                            
                            if r > 1 and val and not val.isspace() and val != "":
                                row_has_value = True
                        
                        sched_rows.append(row_data)
                        if row_has_value:
                            has_actual_content = True
                    
                    if has_actual_content:
                        out_data.append(sched_rows)
                        final_name = sched.Name + ("_" + sufixo if sufixo else "")
                        for char in ['\\', '/', '?', '*', '[', ']', ':']:
                            final_name = final_name.replace(char, '')
                        out_names.append(final_name[:31])

            if not out_data:
                System.Windows.MessageBox.Show("Nenhuma tabela com dados preenchidos foi encontrada usando o filtro: '{}'.".format(filtro_nome), "Aviso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information)
                return

            # Gravação com tratamento de COM seguro via Reflection / Tipagem dinâmica correta
            success = self.write_native_xlsx_safe(file_path, out_names, out_data)

            if success:
                System.Windows.MessageBox.Show("Exportação realizada com sucesso para o ficheiro XLSX!\nForam exportadas {} tabelas para:\n{}".format(len(out_data), file_path), "Sucesso", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Information)
                self.root_window.Close()
            else:
                System.Windows.MessageBox.Show("Houve um erro ao gravar no ficheiro Excel.", "Erro", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error)

        except Exception as ex:
            System.Windows.MessageBox.Show("Erro ao executar a rotina: \n{}".format(str(ex)), "Erro", System.Windows.MessageBoxButton.OK, System.Windows.MessageBoxImage.Error)

    def write_native_xlsx_safe(self, file_path, sheet_names, data_lists):
        excel_app = None
        workbook = None
        try:
            excel_type = System.Type.GetTypeFromProgID("Excel.Application")
            if excel_type is None:
                raise Exception("O Microsoft Excel não está instalado.")
            
            excel_app = System.Activator.CreateInstance(excel_type)
            # Definir propriedades via reflexão para evitar o erro de atribuição direta no __ComObject
            excel_app.GetType().InvokeMember("Visible", System.Reflection.BindingFlags.SetProperty, None, excel_app, System.Array[System.Object]([False]))
            excel_app.GetType().InvokeMember("DisplayAlerts", System.Reflection.BindingFlags.SetProperty, None, excel_app, System.Array[System.Object]([False]))
            
            workbooks = excel_app.GetType().InvokeMember("Workbooks", System.Reflection.BindingFlags.GetProperty, None, excel_app, None)
            
            if os.path.exists(file_path):
                workbook = workbooks.GetType().InvokeMember("Open", System.Reflection.BindingFlags.InvokeMethod, None, workbooks, System.Array[System.Object]([file_path]))
            else:
                workbook = workbooks.GetType().InvokeMember("Add", System.Reflection.BindingFlags.InvokeMethod, None, workbooks, None)
            
            sheets = workbook.GetType().InvokeMember("Sheets", System.Reflection.BindingFlags.GetProperty, None, workbook, None)
            
            for name, rows in zip(sheet_names, data_lists):
                sheet = None
                count = sheets.GetType().InvokeMember("Count", System.Reflection.BindingFlags.GetProperty, None, sheets, None)
                
                for i in range(1, count + 1):
                    sh = sheets.GetType().InvokeMember("Item", System.Reflection.BindingFlags.GetProperty, None, sheets, System.Array[System.Object]([i]))
                    sh_name = sh.GetType().InvokeMember("Name", System.Reflection.BindingFlags.GetProperty, None, sh, None)
                    if sh_name == name:
                        sheet = sh
                        break
                
                if sheet is None:
                    # Adiciona nova folha após a última
                    last_sheet = sheets.GetType().InvokeMember("Item", System.Reflection.BindingFlags.GetProperty, None, sheets, System.Array[System.Object]([count]))
                    sheet = sheets.GetType().InvokeMember("Add", System.Reflection.BindingFlags.InvokeMethod, None, sheets, System.Array[System.Object]([System.Reflection.Missing.Value, last_sheet]))
                    sheet.GetType().InvokeMember("Name", System.Reflection.BindingFlags.SetProperty, None, sheet, System.Array[System.Object]([name]))
                else:
                    cells = sheet.GetType().InvokeMember("Cells", System.Reflection.BindingFlags.GetProperty, None, sheet, None)
                    cells.GetType().InvokeMember("Clear", System.Reflection.BindingFlags.InvokeMethod, None, cells, None)
                
                num_rows = len(rows)
                if num_rows == 0:
                    continue
                num_cols = len(rows[0])
                
                arr = System.Array.CreateInstance(System.Object, num_rows, num_cols)
                for r in range(num_rows):
                    for c in range(num_cols):
                        arr.SetValue(rows[r][c], r, c)
                
                start_cell = sheet.GetType().InvokeMember("Cells", System.Reflection.BindingFlags.GetProperty, None, sheet, System.Array[System.Object]([1, 1]))
                end_cell = sheet.GetType().InvokeMember("Cells", System.Reflection.BindingFlags.GetProperty, None, sheet, System.Array[System.Object]([num_rows, num_cols]))
                range_cells = sheet.GetType().InvokeMember("Range", System.Reflection.BindingFlags.GetProperty, None, sheet, System.Array[System.Object]([start_cell, end_cell]))
                range_cells.GetType().InvokeMember("Value2", System.Reflection.BindingFlags.SetProperty, None, range_cells, System.Array[System.Object]([arr]))
            
            workbook.GetType().InvokeMember("SaveAs", System.Reflection.BindingFlags.InvokeMethod, None, workbook, System.Array[System.Object]([file_path]))
            return True
        except Exception as ex:
            print(str(ex))
            return False
        finally:
            if workbook:
                try:
                    workbook.GetType().InvokeMember("Close", System.Reflection.BindingFlags.InvokeMethod, None, workbook, System.Array[System.Object]([True]))
                except:
                    pass
            if excel_app:
                try:
                    excel_app.GetType().InvokeMember("Quit", System.Reflection.BindingFlags.InvokeMethod, None, excel_app, None)
                except:
                    pass

if __name__ == '__main__':
    script_dir = os.path.dirname(__file__)
    xaml_file = os.path.join(script_dir, "UI.xaml")
    
    if os.path.exists(xaml_file):
        window = ExportWindow(xaml_file)
        window.root_window.ShowDialog()
    else:
        print("Ficheiro UI.xaml não encontrado na pasta do script.")