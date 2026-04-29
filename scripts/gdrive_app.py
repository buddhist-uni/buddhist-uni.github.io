import sys
import os
import subprocess
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QListWidget, QListWidgetItem,
                               QPushButton, QLineEdit, QSplitter,
                               QListWidget, QListView)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap

import pytablericons
from pytablericons.outline_icon import OutlineIcon
from pytablericons.filled_icon import FilledIcon

from gdrive import gcache

from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPainter

def get_icon(icon_enum, is_filled=False, color: Optional[str] = None) -> QIcon:
    if color is None:
        if QApplication.instance():
            color = QApplication.palette().windowText().color().name()
        else:
            color = "#000000"
    
    icon_type = 'filled' if is_filled else 'outline'
    svg_path = os.path.join(pytablericons.__path__[0], 'icons', icon_type, icon_enum.value)
    
    with open(svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()
        
    if is_filled:
        svg_content = svg_content.replace('fill="currentColor"', f'fill="{color}"')
    else:
        svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
        
    renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
    
    size = 128
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    
    return QIcon(pixmap)

def get_mime_icon(mime_type: str) -> QIcon:
    color = QApplication.palette().windowText().color().name()
    if mime_type == 'application/vnd.google-apps.folder':
        return get_icon(FilledIcon.FOLDER, is_filled=True, color=color)
    elif mime_type == 'application/vnd.google-apps.document':
        return get_icon(OutlineIcon.FILE_TEXT, color="#4285F4")
    elif mime_type == 'application/vnd.google-apps.spreadsheet':
        return get_icon(OutlineIcon.FILE_SPREADSHEET, color="#0F9D58")
    elif mime_type == 'application/vnd.google-apps.presentation':
        return get_icon(OutlineIcon.FILE_PRESENTATION, color="#F4B400")
    elif mime_type == 'application/pdf':
        return get_icon(OutlineIcon.FILE_TYPE_PDF, color="#DB4437")
    elif mime_type.startswith('image/'):
        return get_icon(OutlineIcon.PHOTO, color="#DB4437")
    elif mime_type.startswith('audio/'):
        return get_icon(OutlineIcon.FILE_MUSIC, color="#E91E63")
    elif mime_type.startswith('video/'):
        return get_icon(OutlineIcon.MOVIE, color="#FF9800")
    elif 'epub' in mime_type or 'ebook' in mime_type:
        return get_icon(OutlineIcon.BOOK_2, color="#4CAF50")
    elif mime_type == 'application/zip':
        return get_icon(OutlineIcon.FILE_ZIP, color="#9C27B0")
    else:
        return get_icon(OutlineIcon.FILE, color=color)

class GDriveApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Google Drive Explorer")
        self.resize(1000, 600)
        
        self.history = []
        self.history_index = -1
        self.current_folder_id = None
        
        self.init_ui()
        self.load_root("my_drive")

    def init_ui(self):
        central_widget = QSplitter(Qt.Horizontal)
        self.setCentralWidget(central_widget)
        
        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.nav_list = QListWidget()
        self.nav_list.setIconSize(QSize(24, 24))
        my_drive_item = QListWidgetItem("My Drive")
        my_drive_item.setIcon(get_icon(OutlineIcon.BRAND_GOOGLE_DRIVE))
        my_drive_item.setData(Qt.UserRole, "my_drive")
        self.nav_list.addItem(my_drive_item)
        
        shared_item = QListWidgetItem("Shared with me")
        shared_item.setIcon(get_icon(OutlineIcon.USERS))
        shared_item.setData(Qt.UserRole, "shared_with_me")
        self.nav_list.addItem(shared_item)
        
        self.nav_list.itemClicked.connect(self.on_nav_clicked)
        left_layout.addWidget(self.nav_list)
        
        # Right Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top Bar
        top_bar = QHBoxLayout()
        self.back_btn = QPushButton()
        self.back_btn.setIcon(get_icon(OutlineIcon.ARROW_LEFT))
        self.back_btn.clicked.connect(self.go_back)
        
        self.fwd_btn = QPushButton()
        self.fwd_btn.setIcon(get_icon(OutlineIcon.ARROW_RIGHT))
        self.fwd_btn.clicked.connect(self.go_forward)
        
        self.address_bar = QLineEdit()
        self.address_bar.setReadOnly(True)
        
        top_bar.addWidget(self.back_btn)
        top_bar.addWidget(self.fwd_btn)
        top_bar.addWidget(self.address_bar)
        
        right_layout.addLayout(top_bar)
        
        # Main File View
        self.file_view = QListWidget()
        self.file_view.setViewMode(QListView.IconMode)
        self.file_view.setIconSize(QSize(64, 64))
        self.file_view.setResizeMode(QListView.Adjust)
        self.file_view.setSpacing(10)
        self.file_view.setWordWrap(True)
        self.file_view.itemActivated.connect(self.on_item_activated)
        
        right_layout.addWidget(self.file_view)
        
        central_widget.addWidget(left_panel)
        central_widget.addWidget(right_panel)
        central_widget.setSizes([200, 800])
        
        self.update_nav_buttons()
        self.file_view.setFocus()

    def load_root(self, root_type: str, add_history=True):
        if root_type == "my_drive":
            items = gcache.get_root_my_drive_children()
            self.address_bar.setText("My Drive")
        else:
            items = gcache.get_root_shared_with_me_items()
            self.address_bar.setText("Shared with me")
            
        self.current_folder_id = root_type
        if add_history:
            self.add_to_history(root_type)
        self.populate_files(items)

    def load_folder(self, folder_id: str, folder_name: str, add_history=True):
        items = gcache.get_children(folder_id)
        self.current_folder_id = folder_id
        self.address_bar.setText(folder_name)
        if add_history:
            self.add_to_history(folder_id)
        self.populate_files(items)

    def add_to_history(self, folder_id: str):
        # Trim future history if we navigated back then clicked a new folder
        self.history = self.history[:self.history_index + 1]
        self.history.append((folder_id, self.address_bar.text()))
        self.history_index += 1
        self.update_nav_buttons()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            folder_id, name = self.history[self.history_index]
            self._load_from_history(folder_id, name)

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            folder_id, name = self.history[self.history_index]
            self._load_from_history(folder_id, name)

    def _load_from_history(self, folder_id: str, name: str):
        if folder_id in ["my_drive", "shared_with_me"]:
            self.load_root(folder_id, add_history=False)
        else:
            self.load_folder(folder_id, name, add_history=False)
        self.update_nav_buttons()

    def update_nav_buttons(self):
        self.back_btn.setEnabled(self.history_index > 0)
        self.fwd_btn.setEnabled(self.history_index < len(self.history) - 1)

    def on_nav_clicked(self, item: QListWidgetItem):
        root_type = item.data(Qt.UserRole)
        self.load_root(root_type)

    def populate_files(self, items: List[Dict[str, Any]]):
        self.file_view.clear()
        
        # Sort folders first, then files, both alphabetically
        folders = []
        files = []
        for item in items:
            mime = item.get('mimeType', '')
            if mime == 'application/vnd.google-apps.folder':
                folders.append(item)
            else:
                files.append(item)
                
        folders.sort(key=lambda x: x.get('name', '').lower())
        files.sort(key=lambda x: x.get('name', '').lower())
        
        for item in folders + files:
            name = item.get('name', 'Unknown')
            mime = item.get('mimeType', '')
            
            list_item = QListWidgetItem(name)
            list_item.setIcon(get_mime_icon(mime))
            list_item.setData(Qt.UserRole, item)
            self.file_view.addItem(list_item)

    def on_item_activated(self, item: QListWidgetItem):
        file_data = item.data(Qt.UserRole)
        mime = file_data.get('mimeType', '')
        
        if mime == 'application/vnd.google-apps.folder':
            self.load_folder(file_data['id'], file_data['name'])
        else:
            self.open_file(file_data)

    def open_file(self, file_data: Dict[str, Any]):
        cache_path = gcache.get_cache_path_for_file(file_data)
        if cache_path and cache_path.exists():
            # Open with default app
            if sys.platform.startswith('linux'):
                subprocess.Popen(['xdg-open', str(cache_path)], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(cache_path)], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.startfile(str(cache_path))
        else:
            # Placeholder for download
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Not in Cache", 
                                  f"'{file_data.get('name')}' is not downloaded yet.\nDownloading will be implemented later.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace:
            self.go_back()
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Try to set a modern style
    app.setStyle("Fusion")
    
    window = GDriveApp()
    window.show()
    sys.exit(app.exec())
