import sys
import os
import subprocess
import webbrowser
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

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
from PySide6.QtCore import QByteArray, Qt, QRunnable, Signal, QThreadPool, Slot, QTimer
from PySide6.QtGui import QPainter, QImage

from collections import OrderedDict
from functools import lru_cache
import pdfutils as pdfutils
import gdrive_base as gdrive_base
from strutils import thumbnail_path_for_file


class ThumbnailWorker(QRunnable):
    def __init__(self, item, cancel_flag, emit_callback):
        super().__init__()
        self.item = item
        self.cancel_flag = cancel_flag
        self.emit_callback = emit_callback

    def is_cancelled(self):
        return self.cancel_flag[0]

    @Slot()
    def run(self):
        if self.is_cancelled():
            return
        self._process_item(self.item)

    def _process_item(self, item):
        file_id = item.get('id', '')
        mime = item.get('mimeType', '')
        img = None
        
        try:
            from gdrive import gcache
            cache_path = gcache.get_cache_path_for_file(item)
            
            if self.is_cancelled(): return

            if cache_path and cache_path.exists():
                if mime == 'application/pdf':
                    thumbnail_bytes = pdfutils.get_cached_pdf_thumbnail(cache_path, size='large')
                    img = QImage()
                    img.loadFromData(thumbnail_bytes)
            else:
                thumb_path = thumbnail_path_for_file(f"gdrive_{file_id}", size='large')
                if thumb_path.exists():
                    img = QImage(str(thumb_path))
                else:
                    if mime == 'application/pdf':
                        if self.is_cancelled(): return
                        thumbnail_bytes = gdrive_base.fetch_preview_image(file_id, size=256)
                        if thumbnail_bytes:
                            if self.is_cancelled(): return
                            img = QImage()
                            img.loadFromData(thumbnail_bytes)
                            thumb_path.parent.mkdir(parents=True, exist_ok=True)
                            thumb_path.write_bytes(thumbnail_bytes)
        except Exception as e:
            if not self.is_cancelled():
                print(f"Error fetching thumbnail for {file_id}: {e}")
            
        if img and not img.isNull() and not self.is_cancelled():
            self.emit_callback(file_id, img)

class LRUCache:
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

@lru_cache(maxsize=None)
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
    elif mime_type == 'application/vnd.google-apps.shortcut+file':
        return get_icon(OutlineIcon.FILE_SYMLINK, color="#999999")
    elif mime_type == 'application/vnd.google-apps.shortcut+folder':
        return get_icon(OutlineIcon.FOLDER_SYMLINK, color="#999999")
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

@dataclass
class HistoryEntry:
    id: str
    name: str
    clicked_item_id: Optional[str] = None

class GDriveApp(QMainWindow):
    thumbnail_loaded_signal = Signal(str, QImage)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Google Drive Explorer")
        self.resize(1000, 600)
        
        self.history: List[HistoryEntry] = []
        self.history_index = -1
        self.current_folder_id = None
        
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(10)
        self.thumbnail_cache = LRUCache(500)
        self.item_mapping: Dict[str, QListWidgetItem] = {}
        self.current_cancel_flag = [False]
        self.queued_thumbnails = set()
        self.thumbnail_loaded_signal.connect(self.on_thumbnail_loaded)
        
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
        self.file_view.setIconSize(QSize(128, 128))
        self.file_view.setResizeMode(QListView.Adjust)
        self.file_view.setSpacing(10)
        self.file_view.setWordWrap(True)
        # Set a fixed grid size to constrain item width, which forces the default 
        # WrapAtWordBoundaryOrAnywhere behavior to actually wrap instead of expanding the item.
        self.file_view.setGridSize(QSize(160, 200))
        self.file_view.itemActivated.connect(self.on_item_activated)
        
        right_layout.addWidget(self.file_view)
        
        central_widget.addWidget(left_panel)
        central_widget.addWidget(right_panel)
        central_widget.setSizes([200, 800])
        
        self.update_nav_buttons()
        self.file_view.verticalScrollBar().valueChanged.connect(self.update_visible_thumbnails)
        self.file_view.setFocus()

    def load_root(self, root_type: str, add_history=True, highlight_fileid: str | None = None, clicked_item_id: str | None = None):
        if root_type == "my_drive":
            items = gcache.get_root_my_drive_children()
            self.address_bar.setText("My Drive")
        else:
            items = gcache.get_root_shared_with_me_items()
            self.address_bar.setText("Shared with me")
            
        self.current_folder_id = root_type
        if add_history:
            self.add_to_history(root_type, clicked_item_id)
        self.populate_files(items)
        if highlight_fileid and highlight_fileid in self.item_mapping:
            item = self.item_mapping[highlight_fileid]
            item.setSelected(True)
            self.file_view.setCurrentItem(item)
        self.file_view.repaint()

    def load_folder(self, folder_id: str, folder_name: str, add_history=True, highlight_fileid: str | None=None, clicked_item_id: str | None = None):
        items = gcache.get_children(folder_id)
        self.current_folder_id = folder_id
        self.address_bar.setText(folder_name)
        if add_history:
            self.add_to_history(folder_id, clicked_item_id)
        self.populate_files(items)
        if highlight_fileid and highlight_fileid in self.item_mapping:
            item = self.item_mapping[highlight_fileid]
            item.setSelected(True)
            self.file_view.setCurrentItem(item)
        self.file_view.repaint() # Don't let QT wait for the async thumbnails

    def add_to_history(self, folder_id: str, clicked_item_id: str | None = None):
        # Trim future history if we navigated back then clicked a new folder
        self.history = self.history[:self.history_index + 1]
        self.history.append(HistoryEntry(
            id=folder_id,
            name=self.address_bar.text(),
            clicked_item_id=clicked_item_id
        ))
        self.history_index += 1
        self.update_nav_buttons()

    def go_back(self):
        if self.history_index > 0:
            current_entry = self.history[self.history_index]
            self.history_index -= 1
            prev_entry = self.history[self.history_index]
            self._load_from_history(prev_entry.id, prev_entry.name, highlight_fileid=current_entry.clicked_item_id)

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            entry = self.history[self.history_index]
            self._load_from_history(entry.id, entry.name)

    def _load_from_history(self, folder_id: str, name: str, highlight_fileid: str | None = None):
        if folder_id in ["my_drive", "shared_with_me"]:
            self.load_root(folder_id, add_history=False, highlight_fileid=highlight_fileid)
        else:
            self.load_folder(folder_id, name, add_history=False, highlight_fileid=highlight_fileid)
        self.update_nav_buttons()

    def update_nav_buttons(self):
        self.back_btn.setEnabled(self.history_index > 0)
        self.fwd_btn.setEnabled(self.history_index < len(self.history) - 1)

    def on_nav_clicked(self, item: QListWidgetItem):
        root_type = item.data(Qt.UserRole)
        self.load_root(root_type)

    def populate_files(self, items: List[Dict[str, Any]]):
        if hasattr(self, 'current_cancel_flag'):
            self.current_cancel_flag[0] = True
        self.current_cancel_flag = [False]
        self.thumbnail_pool.clear()
        self.queued_thumbnails.clear()
        
        self.file_view.clear()
        self.item_mapping.clear()
        
        # Show folders, then folder shortcuts, then files
        folders = []
        folder_shortcuts = []
        files = []
        items_needing_thumbnails = []
        for item in items:
            mime = item.get('mimeType', '')
            if mime == 'application/vnd.google-apps.folder':
                folders.append(item)
            elif mime == 'application/vnd.google-apps.shortcut' and item['shortcutDetails']['targetMimeType'] == 'application/vnd.google-apps.folder':
                folder_shortcuts.append(item)
            else:
                files.append(item)

        sortkey = lambda x: x.get('name', '').lower()
        folders.sort(key=sortkey)
        folder_shortcuts.sort(key=sortkey)
        files.sort(key=sortkey)
        
        for item in folders + folder_shortcuts + files:
            name = item.get('name', 'Unknown')
            mime = item.get('mimeType', '')
            if item.get('shortcutDetails'):
                if item['shortcutDetails']['targetMimeType'] == 'application/vnd.google-apps.folder':
                    mime += '+folder'
                else:
                    mime += "+file"
            file_id = item.get('id', '')
            
            list_item = QListWidgetItem(name)
            
            cached_pixmap = self.thumbnail_cache.get(file_id)
            if cached_pixmap:
                list_item.setIcon(QIcon(cached_pixmap))
            else:
                list_item.setIcon(get_mime_icon(mime))
                if mime == 'application/pdf':
                    items_needing_thumbnails.append(item)
            
            list_item.setData(Qt.UserRole, item)
            self.file_view.addItem(list_item)
            self.item_mapping[file_id] = list_item
        
        QTimer.singleShot(0, self.update_visible_thumbnails)
        self.file_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def update_visible_thumbnails(self):
        viewport_rect = self.file_view.viewport().rect()
        # Expand rect to load items slightly out of view
        expanded_rect = viewport_rect.adjusted(0, -viewport_rect.height(), 0, viewport_rect.height())
        
        for i in range(self.file_view.count()):
            item = self.file_view.item(i)
            file_data = item.data(Qt.UserRole)
            mime = file_data.get('mimeType', '')
            file_id = file_data.get('id', '')
            
            if mime == 'application/pdf' and file_id not in self.queued_thumbnails:
                if not self.thumbnail_cache.get(file_id):
                    item_rect = self.file_view.visualItemRect(item)
                    if expanded_rect.intersects(item_rect):
                        self.queued_thumbnails.add(file_id)
                        worker = ThumbnailWorker(
                            file_data,
                            self.current_cancel_flag,
                            self.thumbnail_loaded_signal.emit
                        )
                        self.thumbnail_pool.start(worker)

    def on_thumbnail_loaded(self, file_id: str, img: QImage):
        pixmap = QPixmap.fromImage(img)
        self.thumbnail_cache.put(file_id, pixmap)
        if file_id in self.item_mapping:
            item = self.item_mapping[file_id]
            if item.listWidget() == self.file_view:
                item.setIcon(QIcon(pixmap))

    def on_item_activated(self, item: QListWidgetItem):
        file_data = item.data(Qt.UserRole)
        mime = file_data.get('mimeType', '')
        
        if mime == 'application/vnd.google-apps.folder':
            self.load_folder(file_data['id'], file_data['name'], clicked_item_id=file_data['id'])
        elif mime == 'application/vnd.google-apps.shortcut':
            if file_data['shortcutDetails']['targetMimeType'] == 'application/vnd.google-apps.folder':
                folder_id = file_data['shortcutDetails']['targetId']
                target_file = None
            else:
                target_file = gcache.get_item(file_data['shortcutDetails']['targetId'])
                folder_id = target_file['parent_id']
                target_file = target_file['id']
            target_folder = gcache.get_item(folder_id)
            if not target_folder:
                url = gdrive_base.FOLDER_LINK.format(folder_id)
                webbrowser.open(url)
            self.load_folder(target_folder['id'], target_folder['name'], highlight_fileid=target_file, clicked_item_id=file_data['id'])
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
            url = gdrive_base.GENERIC_LINK_PREFIX + file_data['id']
            webbrowser.open(url)

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
