# -*- coding: utf-8 -*-
import sys
import re
import clr

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
clr.AddReference('PresentationFramework')
import System
import Autodesk.Revit.DB as DB
import Autodesk.Revit.UI as UI

from pyrevit import forms, script

uidoc = __revit__.ActiveUIDocument
doc = uidoc.Document


class RoomItem(object):
    def __init__(self, room, link_instance=None):
        self.Room = room
        self.LinkInstance = link_instance  # None se for do arquivo hospedeiro
        
        param_name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
        self.RoomName = param_name.AsString() if param_name else "Ambiente"
        
        level_id = room.LevelId
        # Se o ambiente for do link, buscamos o nível no documento do link
        target_doc = link_instance.GetLinkDocument() if link_instance else doc
        level = target_doc.GetElement(level_id) if level_id else None
        level_name = level.Name if level else "Sem Nível"
        
        link_prefix = "[VINCULADO] " if link_instance else ""
        self.NameAndLevel = "{}{} ({})".format(link_prefix, self.RoomName, level_name)


class ViewTemplateItem(object):
    def __init__(self, view):
        self.View = view
        self.Name = view.Name if view else "Nenhum (Padrão)"


class ElevationTypeItem(object):
    def __init__(self, elev_type):
        self.ElevationType = elev_type
        param_name = elev_type.get_Parameter(DB.BuiltInParameter.ALL_MODEL_TYPE_NAME)
        self.Name = param_name.AsString() if param_name else "Tipo Padrão"


class SheetItem(object):
    def __init__(self, sheet):
        self.Sheet = sheet
        sheet_number = sheet.SheetNumber
        sheet_name = sheet.Name
        self.Name = "{} - {}".format(sheet_number, sheet_name)


class TitleBlockParamItem(object):
    def __init__(self, param_name):
        self.Name = param_name
        self.IsChecked = False


class RoomSelectorWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name, rooms, floor_templates, d3_templates, elevation_templates, elevation_types, sheets, title_blocks):
        forms.WPFWindow.__init__(self, xaml_file_name)
        self.all_rooms = rooms
        self.title_blocks = title_blocks
        self.SelectedRoomItems = []
        self.OffsetValue = 15.0
        
        self.CreateFloorPlan = True
        self.Create3D = True
        self.CreateElevations = True
        
        self.SelectedFloorTemplate = None
        self.Selected3DTemplate = None
        self.SelectedElevationTemplate = None
        self.SelectedElevationType = None
        
        self.PlaceOnSheet = False
        self.SheetMode = 0
        self.SelectedSheet = None
        self.NewSheetNumber = ""
        self.NewSheetName = ""
        self.SelectedTitleBlock = None
        self.SelectedParameters = []
        
        if hasattr(self, 'RoomsListBox'):
            self.update_room_list("")

        filter_box = getattr(self, 'FilterTextBox', None)
        if filter_box:
            filter_box.TextChanged += self.filter_text_changed

        if hasattr(self, 'FloorPlanTemplateComboBox'):
            self.FloorPlanTemplateComboBox.ItemsSource = floor_templates
            self.FloorPlanTemplateComboBox.SelectedIndex = 0

        if hasattr(self, 'View3DTemplateComboBox'):
            self.View3DTemplateComboBox.ItemsSource = d3_templates
            self.View3DTemplateComboBox.SelectedIndex = 0

        if hasattr(self, 'ElevationTemplateComboBox'):
            self.ElevationTemplateComboBox.ItemsSource = elevation_templates
            self.ElevationTemplateComboBox.SelectedIndex = 0

        if hasattr(self, 'ElevationTypeComboBox'):
            self.ElevationTypeComboBox.ItemsSource = elevation_types
            if elevation_types:
                self.ElevationTypeComboBox.SelectedIndex = 0

        if hasattr(self, 'SheetComboBox'):
            self.SheetComboBox.ItemsSource = sheets
            self.SheetComboBox.SelectedIndex = 0

        if hasattr(self, 'TitleBlockComboBox'):
            self.TitleBlockComboBox.ItemsSource = title_blocks
            if title_blocks:
                self.TitleBlockComboBox.SelectedIndex = 0
            self.TitleBlockComboBox.SelectionChanged += self.titleblock_changed

        if hasattr(self, 'PlaceOnSheetCheckBox'):
            self.PlaceOnSheetCheckBox.Checked += self.sheet_option_changed
            self.PlaceOnSheetCheckBox.Unchecked += self.sheet_option_changed

        if hasattr(self, 'SheetModeComboBox'):
            self.SheetModeComboBox.ItemsSource = ["Selecionar Existente", "Criar Nova Folha Única", "Criar Uma Folha por Ambiente"]
            self.SheetModeComboBox.SelectedIndex = 0
            self.SheetModeComboBox.SelectionChanged += self.sheet_mode_changed

        self.update_ui_states()
        if title_blocks:
            self.load_titleblock_parameters(title_blocks[0])

    def titleblock_changed(self, sender, e):
        if hasattr(self, 'TitleBlockComboBox') and self.TitleBlockComboBox.SelectedItem:
            self.load_titleblock_parameters(self.TitleBlockComboBox.SelectedItem)

    def load_titleblock_parameters(self, tb_symbol):
        param_items = []
        seen_names = set()
        
        t = DB.Transaction(doc, "Temp Read Parameters")
        t.Start()
        temp_sheet = None
        try:
            temp_sheet = DB.ViewSheet.Create(doc, tb_symbol.Id)
            doc.Regenerate()
            
            tb_collector = DB.FilteredElementCollector(doc, temp_sheet.Id).OfCategory(DB.BuiltInCategory.OST_TitleBlocks).WhereElementIsNotElementType().ToElements()
            for tb in tb_collector:
                iterator = tb.Parameters.GetEnumerator()
                while iterator.MoveNext():
                    param = iterator.Current
                    if param.StorageType == DB.StorageType.Integer and not param.IsReadOnly:
                        p_name = param.Definition.Name
                        if p_name and p_name not in seen_names and not p_name.startswith("ELEM_"):
                            seen_names.add(p_name)
                            param_items.append(TitleBlockParamItem(p_name))
        except Exception:
            pass
        
        if temp_sheet:
            try:
                doc.Delete(temp_sheet.Id)
            except:
                pass
        t.RollBack()

        if hasattr(self, 'ParametersListBox'):
            self.ParametersListBox.ItemsSource = param_items

    def sheet_option_changed(self, sender, e):
        self.update_ui_states()

    def sheet_mode_changed(self, sender, e):
        self.update_ui_states()

    def update_ui_states(self):
        place_checked = self.PlaceOnSheetCheckBox.IsChecked if hasattr(self, 'PlaceOnSheetCheckBox') else False
        
        if hasattr(self, 'SheetOptionsPanel'):
            self.SheetOptionsPanel.Visibility = System.Windows.Visibility.Visible if place_checked else System.Windows.Visibility.Collapsed

        if place_checked and hasattr(self, 'SheetModeComboBox'):
            mode = self.SheetModeComboBox.SelectedIndex
            if hasattr(self, 'ExistingSheetPanel') and hasattr(self, 'NewSheetPanel') and hasattr(self, 'NewSheetNameStack') and hasattr(self, 'SheetParametersPanel'):
                if mode == 0:
                    self.ExistingSheetPanel.Visibility = System.Windows.Visibility.Visible
                    self.NewSheetPanel.Visibility = System.Windows.Visibility.Collapsed
                    self.SheetParametersPanel.Visibility = System.Windows.Visibility.Collapsed
                elif mode == 1:
                    self.ExistingSheetPanel.Visibility = System.Windows.Visibility.Collapsed
                    self.NewSheetPanel.Visibility = System.Windows.Visibility.Visible
                    self.NewSheetNameStack.Visibility = System.Windows.Visibility.Visible
                    self.SheetParametersPanel.Visibility = System.Windows.Visibility.Visible
                elif mode == 2:
                    self.ExistingSheetPanel.Visibility = System.Windows.Visibility.Collapsed
                    self.NewSheetPanel.Visibility = System.Windows.Visibility.Visible
                    self.NewSheetNameStack.Visibility = System.Windows.Visibility.Collapsed
                    self.SheetParametersPanel.Visibility = System.Windows.Visibility.Visible

    def update_room_list(self, filter_string):
        filter_lower = filter_string.lower()
        filtered = []
        for r_item in self.all_rooms:
            if filter_lower in r_item.NameAndLevel.lower():
                filtered.append(r_item)
        self.RoomsListBox.ItemsSource = filtered

    def filter_text_changed(self, sender, e):
        filter_box = getattr(self, 'FilterTextBox', None)
        if filter_box:
            self.update_room_list(filter_box.Text)

    def SelectButton_Click(self, sender, e):
        selected_items = self.RoomsListBox.SelectedItems if hasattr(self, 'RoomsListBox') else []
        
        if not selected_items:
            forms.alert("Nenhum ambiente foi selecionado na lista.", title="Aviso")
            return

        self.CreateFloorPlan = self.CreateFloorPlanCheckBox.IsChecked if hasattr(self, 'CreateFloorPlanCheckBox') else True
        self.Create3D = self.Create3DCheckBox.IsChecked if hasattr(self, 'Create3DCheckBox') else True
        self.CreateElevations = self.CreateElevationsCheckBox.IsChecked if hasattr(self, 'CreateElevationsCheckBox') else True

        if not self.CreateFloorPlan and not self.Create3D and not self.CreateElevations:
            forms.alert("Deve selecionar pelo menos um tipo de vista para gerar.", title="Aviso")
            return

        offset_text = self.OffsetTextBox.Text.replace(',', '.') if hasattr(self, 'OffsetTextBox') else "15"
        try:
            self.OffsetValue = float(offset_text)
        except ValueError:
            forms.alert("Por favor, introduza um valor numérico válido para o offset.", title="Erro")
            return

        self.SelectedRoomItems = list(selected_items)

        if hasattr(self, 'FloorPlanTemplateComboBox') and self.FloorPlanTemplateComboBox.SelectedItem:
            self.SelectedFloorTemplate = getattr(self.FloorPlanTemplateComboBox.SelectedItem, 'View', None)

        if hasattr(self, 'View3DTemplateComboBox') and self.View3DTemplateComboBox.SelectedItem:
            self.Selected3DTemplate = getattr(self.View3DTemplateComboBox.SelectedItem, 'View', None)

        if hasattr(self, 'ElevationTemplateComboBox') and self.ElevationTemplateComboBox.SelectedItem:
            self.SelectedElevationTemplate = getattr(self.ElevationTemplateComboBox.SelectedItem, 'View', None)

        if hasattr(self, 'ElevationTypeComboBox') and self.ElevationTypeComboBox.SelectedItem:
            self.SelectedElevationType = getattr(self.ElevationTypeComboBox.SelectedItem, 'ElevationType', None)

        self.PlaceOnSheet = self.PlaceOnSheetCheckBox.IsChecked if hasattr(self, 'PlaceOnSheetCheckBox') else False

        if self.PlaceOnSheet:
            self.SheetMode = self.SheetModeComboBox.SelectedIndex if hasattr(self, 'SheetModeComboBox') else 0
            if self.SheetMode == 0:
                if hasattr(self, 'SheetComboBox') and self.SheetComboBox.SelectedItem:
                    self.SelectedSheet = getattr(self.SheetComboBox.SelectedItem, 'Sheet', None)
            else:
                self.NewSheetNumber = self.NewSheetNumberTextBox.Text.strip() if hasattr(self, 'NewSheetNumberTextBox') else ""
                if not self.NewSheetNumber:
                    forms.alert("Por favor, insira o número da folha.", title="Erro")
                    return
                if self.SheetMode == 1:
                    self.NewSheetName = self.NewSheetNameTextBox.Text.strip() if hasattr(self, 'NewSheetNameTextBox') else ""

            if hasattr(self, 'TitleBlockComboBox') and self.TitleBlockComboBox.SelectedItem:
                self.SelectedTitleBlock = self.TitleBlockComboBox.SelectedItem

            if hasattr(self, 'ParametersListBox') and self.ParametersListBox.ItemsSource:
                self.SelectedParameters = [item for item in self.ParametersListBox.ItemsSource if item.IsChecked]

        self.Close()


def get_room_bounding_box(room, offset_internal, transform=None):
    param_name = room.get_Parameter(DB.BuiltInParameter.ROOM_NAME)
    room_name = param_name.AsString() if param_name else "Ambiente"

    bbox = room.get_BoundingBox(None)
    if not bbox:
        bbox = DB.BoundingBoxXYZ()
        bbox.Min = DB.XYZ(-5, -5, 0)
        bbox.Max = DB.XYZ(5, 5, 3)

    min_p = DB.XYZ(bbox.Min.X - offset_internal, bbox.Min.Y - offset_internal, bbox.Min.Z - offset_internal)
    max_p = DB.XYZ(bbox.Max.X + offset_internal, bbox.Max.Y + offset_internal, bbox.Max.Z + offset_internal)

    # Se o ambiente pertencer a um arquivo vinculado, precisamos transformar as coordenadas para o arquivo hospedeiro
    if transform:
        min_p = transform.OfPoint(min_p)
        max_p = transform.OfPoint(max_p)

    new_bbox = DB.BoundingBoxXYZ()
    new_bbox.Min = min_p
    new_bbox.Max = max_p

    return new_bbox, room_name


def get_room_center_point(room, transform=None):
    pt = DB.XYZ.Zero
    if hasattr(room, 'Location') and room.Location and hasattr(room.Location, 'Point'):
        pt = room.Location.Point
        bbox = room.get_BoundingBox(None)
        if bbox:
            z_elevation = (bbox.Min.Z + bbox.Max.Z) / 2.0
            pt = DB.XYZ(pt.X, pt.Y, z_elevation)
    else:
        bbox = room.get_BoundingBox(None)
        if bbox:
            pt = DB.XYZ((bbox.Min.X + bbox.Max.X) / 2.0, (bbox.Min.Y + bbox.Max.Y) / 2.0, (bbox.Min.Z + bbox.Max.Z) / 2.0)

    if transform:
        pt = transform.OfPoint(pt)

    return pt


def set_unique_view_name(doc, base_name, view_type_suffix=""):
    name = "{} - {}".format(base_name, view_type_suffix).strip()
    for i in range(50):
        try:
            existing = DB.FilteredElementCollector(doc).OfClass(DB.View).WhereElementIsNotElementType().ToElements()
            names = [v.Name for v in existing]
            if name not in names:
                return name
            name = "{} - {} ({})".format(base_name, view_type_suffix, i + 1).strip()
        except:
            break
    return name


def generate_next_sheet_number(current_number, index):
    if index == 0:
        return current_number
    
    numbers = re.findall(r'\d+', current_number)
    if not numbers:
        return current_number + str(index + 1)
    
    target_num_str = numbers[-1]
    num_len = len(target_num_str)
    
    new_num_val = int(target_num_str) + index
    new_num_str = str(new_num_val).zfill(num_len)
    
    parts = current_number.rpartition(target_num_str)
    return parts[0] + new_num_str + parts[2]


def apply_titleblock_parameters(doc, sheet, window):
    tb_collector = DB.FilteredElementCollector(doc, sheet.Id).OfCategory(DB.BuiltInCategory.OST_TitleBlocks).WhereElementIsNotElementType().ToElements()
    for tb in tb_collector:
        selected_names = [p.Name for p in window.SelectedParameters]
        try:
            iterator = tb.Parameters.GetEnumerator()
            while iterator.MoveNext():
                param = iterator.Current
                if param.StorageType == DB.StorageType.Integer and not param.IsReadOnly:
                    p_name = param.Definition.Name
                    val = 1 if p_name in selected_names else 0
                    param.Set(val)
        except Exception:
            pass


def place_views_in_specific_order(doc, sheet, view_dict):
    if not sheet:
        return 0

    placed_count = 0
    row1_y = DB.UnitUtils.ConvertToInternalUnits(350.0, DB.UnitTypeId.Millimeters)
    
    x_plan = DB.UnitUtils.ConvertToInternalUnits(80.0, DB.UnitTypeId.Millimeters)
    x_3d   = DB.UnitUtils.ConvertToInternalUnits(200.0, DB.UnitTypeId.Millimeters)
    x_e1   = DB.UnitUtils.ConvertToInternalUnits(320.0, DB.UnitTypeId.Millimeters)
    
    row2_y = DB.UnitUtils.ConvertToInternalUnits(180.0, DB.UnitTypeId.Millimeters)
    x_e2   = DB.UnitUtils.ConvertToInternalUnits(80.0, DB.UnitTypeId.Millimeters)
    x_e3   = DB.UnitUtils.ConvertToInternalUnits(200.0, DB.UnitTypeId.Millimeters)
    x_e4   = DB.UnitUtils.ConvertToInternalUnits(320.0, DB.UnitTypeId.Millimeters)

    layout_map = {
        '2D': DB.XYZ(x_plan, row1_y, 0),
        '3D': DB.XYZ(x_3d, row1_y, 0),
        'E1': DB.XYZ(x_e1, row1_y, 0),
        'E2': DB.XYZ(x_e2, row2_y, 0),
        'E3': DB.XYZ(x_e3, row2_y, 0),
        'E4': DB.XYZ(x_e4, row2_y, 0)
    }

    for key, pos in layout_map.items():
        v_id = view_dict.get(key)
        if v_id and v_id != DB.ElementId.InvalidElementId:
            try:
                if DB.Viewport.CanAddViewToSheet(doc, sheet.Id, v_id):
                    DB.Viewport.Create(doc, sheet.Id, v_id, pos)