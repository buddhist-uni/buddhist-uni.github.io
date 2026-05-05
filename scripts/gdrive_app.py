import sys
import os
import subprocess
import webbrowser
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QListWidget, QListWidgetItem,
                               QPushButton, QLineEdit, QSplitter, QMessageBox,
                               QListView, QMenu, QProgressDialog, QCompleter,
                               QDialog, QLabel, QInputDialog)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QShortcut, QKeySequence

import pytablericons
from pytablericons.outline_icon import OutlineIcon
from pytablericons.filled_icon import FilledIcon


from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt, QRunnable, Signal, QThreadPool, Slot, QTimer, QThread, QStringListModel
from PySide6.QtGui import QPainter, QImage

from collections import OrderedDict
from functools import lru_cache
import pdfutils
import videoutils
import gdrive_base
from strutils import thumbnail_path_for_file, THUMBNAIL_SIZES


class GCacheLoaderThread(QThread):
    progress_text_changed = Signal(str)
    progress_value_changed = Signal(int, int) # current, total
    
    def run(self):
        import local_gdrive
        import gdrive_base
        
        original_yaspin = getattr(local_gdrive, 'yaspin', None)
        original_trange = getattr(gdrive_base, 'trange', None)
        
        class MockYaspin:
            def __init__(self_mock, *args, **kwargs):
                self_mock.text = kwargs.get('text', args[0] if args else "")
            def __enter__(self_mock):
                self.progress_text_changed.emit(self_mock.text)
                self.progress_value_changed.emit(0, 0)
                return self_mock
            def __exit__(self_mock, exc_type, exc_val, exc_tb):
                pass
            def write(self_mock, text):
                pass
                
        def mock_trange(*args, **kwargs):
            r = range(*args)
            total = len(r)
            self.progress_value_changed.emit(0, total)
            for i, val in enumerate(r):
                self.progress_value_changed.emit(i, total)
                yield val
            self.progress_value_changed.emit(total, total)
            
        local_gdrive.yaspin = MockYaspin # pyrefly: ignore[bad-assignment]
        gdrive_base.trange = mock_trange
        
        try:
            import gdrive
        finally:
            if original_yaspin:
                local_gdrive.yaspin = original_yaspin
            if original_trange:
                gdrive_base.trange = original_trange


class ThumbnailWorker(QRunnable):
    def __init__(self, item, cancel_flag, emit_callback):
        super().__init__()
        self.item = item
        self.cancel_flag = cancel_flag
        self.emit_callback = emit_callback
        self.size = 'normal'

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
            if not cache_path:
                return
            size = THUMBNAIL_SIZES[self.size]
            thumb_path = thumbnail_path_for_file(cache_path, shared=True, size=self.size)
            if thumb_path.exists():
                img = QImage(str(thumb_path))
            elif cache_path.exists():
                if self.is_cancelled(): return
                if mime == 'application/pdf':
                    thumbnail_bytes = pdfutils.get_cached_pdf_thumbnail(cache_path, size=self.size)
                    img = QImage()
                    img.loadFromData(thumbnail_bytes)
                elif mime.startswith('video/'):
                    thumbnail_bytes = videoutils.get_cached_video_thumbnail(cache_path, size=self.size)
                    img = QImage()
                    img.loadFromData(thumbnail_bytes)
            else:
                if mime == 'application/pdf' or mime.startswith('video/'):
                    if self.is_cancelled(): return
                    thumbnail_bytes = gdrive_base.fetch_preview_image(file_id, size=size)
                    if thumbnail_bytes:
                        img = QImage()
                        img.loadFromData(thumbnail_bytes)
                        thumb_path.parent.mkdir(parents=True, exist_ok=True)
                        # Yes, the thumb_path and the gdrive preview_image are both PNG
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
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
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
        return get_icon(OutlineIcon.FOLDER_SYMLINK, color=color)
    elif mime_type == 'application/vnd.google-apps.document':
        return get_icon(OutlineIcon.FILE_TEXT, color="#4285F4")
    elif mime_type == 'application/vnd.google-apps.spreadsheet':
        return get_icon(OutlineIcon.FILE_SPREADSHEET, color="#0F9D58")
    elif mime_type == 'application/vnd.google-apps.presentation':
        return get_icon(OutlineIcon.FILE_POWER, color="#F4B400")
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


class MoveFileDialog(QDialog):
    def __init__(self, parent=None, gcache=None):
        super().__init__(parent)
        self.setWindowTitle("Move File")
        self.setMinimumWidth(400)
        self.gcache = gcache
        self.resulting_tuple = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Move to folder (e.g. 'course/subfolder'):"))
        
        self.line_edit = QLineEdit()
        self.completer = QCompleter()
        self.completer_model = QStringListModel()
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.line_edit.setCompleter(self.completer)
        self.line_edit.textEdited.connect(self.update_completer)
        layout.addWidget(self.line_edit)
        
        buttons = QHBoxLayout()
        self.move_btn = QPushButton("Move")
        self.move_btn.clicked.connect(self.handle_move)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.move_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
        
        self.line_edit.returnPressed.connect(self.handle_move)

    def update_completer(self, text):
        if not text or not self.gcache:
            return
        import gdrive
        suggestions = gdrive.get_course_suggestions(text)
        self.completer_model.setStringList(suggestions)

    def handle_move(self):
        query = self.line_edit.text()
        if not query:
            return
        import gdrive
        try:
            self.resulting_tuple = gdrive.get_gfolders_for_course(query, invite_to_add=False)
            self.accept()
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Not Found", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

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
        
        self.gcache = None
        self.init_ui()
        
        self.progress_dialog = QProgressDialog("Loading GDrive Cache...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Please Wait")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        
        self.loader_thread = GCacheLoaderThread(self)
        self.loader_thread.progress_text_changed.connect(self.progress_dialog.setLabelText)
        self.loader_thread.progress_value_changed.connect(self.update_progress)
        self.loader_thread.finished.connect(self.on_gcache_loaded)
        self.loader_thread.start()

    def update_progress(self, current, total):
        self.progress_dialog.setMaximum(total)
        self.progress_dialog.setValue(current)

    def on_gcache_loaded(self):
        self.progress_dialog.close()
        import gdrive
        self.gcache = gdrive.gcache
        self.load_root("my_drive")

    def init_ui(self):
        central_widget = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(central_widget)
        
        # Left Panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.nav_list = QListWidget()
        self.nav_list.setIconSize(QSize(24, 24))
        my_drive_item = QListWidgetItem("My Drive")
        my_drive_item.setIcon(get_icon(OutlineIcon.BRAND_GOOGLE_DRIVE))
        my_drive_item.setData(Qt.ItemDataRole.UserRole, "my_drive")
        self.nav_list.addItem(my_drive_item)
        
        shared_item = QListWidgetItem("Shared with me")
        shared_item.setIcon(get_icon(OutlineIcon.USERS))
        shared_item.setData(Qt.ItemDataRole.UserRole, "shared_with_me")
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
        
        self.up_btn = QPushButton()
        self.up_btn.setIcon(get_icon(OutlineIcon.ARROW_UP))
        self.up_btn.clicked.connect(self.go_up)
        
        self.address_bar = QLineEdit()
        self.address_bar.returnPressed.connect(self.on_address_bar_return)
        
        self.completer = QCompleter()
        self.completer_model = QStringListModel()
        self.completer.setModel(self.completer_model)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.address_bar.setCompleter(self.completer)
        self.address_bar.textEdited.connect(self.update_completer)
        
        top_bar.addWidget(self.back_btn)
        top_bar.addWidget(self.fwd_btn)
        top_bar.addWidget(self.up_btn)
        top_bar.addWidget(self.address_bar)
        
        right_layout.addLayout(top_bar)
        
        # Main File View
        self.file_view = QListWidget()
        self.file_view.setViewMode(QListView.ViewMode.IconMode)
        self.file_view.setIconSize(QSize(128, 128))
        self.file_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.file_view.setSpacing(10)
        self.file_view.setWordWrap(True)
        # Set a fixed grid size to constrain item width, which forces the default 
        # WrapAtWordBoundaryOrAnywhere behavior to actually wrap instead of expanding the item.
        self.file_view.setGridSize(QSize(160, 200))
        self.file_view.itemActivated.connect(self.on_item_activated)
        self.file_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_view.customContextMenuRequested.connect(self.on_context_menu)
        
        right_layout.addWidget(self.file_view)
        
        central_widget.addWidget(left_panel)
        central_widget.addWidget(right_panel)
        central_widget.setSizes([200, 800])
        
        self.update_nav_buttons()
        self.file_view.verticalScrollBar().valueChanged.connect(self.update_visible_thumbnails)
        
        # Shortcut for context menu (standard on Linux/Ubuntu)
        self.context_shortcut = QShortcut(QKeySequence("Shift+F10"), self)
        self.context_shortcut.activated.connect(self.show_file_view_context_menu)
        
        # Shortcut for renaming
        self.rename_shortcut = QShortcut(QKeySequence("F2"), self)
        self.rename_shortcut.activated.connect(self.trigger_rename)
        
        self.file_view.setFocus()

    def apply_icon_overlay(self, pixmap: QPixmap, icon_enum: Any, color: str | None = None, is_filled: bool = False) -> QPixmap:
        result = QPixmap(pixmap)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not color:
            color = QApplication.palette().text().color().name()
        
        overlay_icon = get_icon(icon_enum, color=color, is_filled=is_filled)
        overlay_size = pixmap.width() // 4
        overlay_pixmap = overlay_icon.pixmap(QSize(overlay_size, overlay_size))
        
        # Position in lower right corner
        x = pixmap.width() - overlay_size - 4
        y = pixmap.height() - overlay_size - 4
        
        # Draw a circular background
        bg_color = QApplication.palette().window().color().name()
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x + 2, y + 2, overlay_size - 4, overlay_size - 4)
        
        painter.drawPixmap(x, y, overlay_pixmap)
        painter.end()
        return result

    def load_root(self, root_type: str, add_history=True, highlight_fileid: str | None = None, clicked_item_id: str | None = None):
        if not self.gcache:
            return
        if root_type == "my_drive":
            items = self.gcache.get_root_my_drive_children()
            self.address_bar.setText("My Drive")
        else:
            items = self.gcache.get_root_shared_with_me_items()
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
        if not self.gcache:
            return
        items = self.gcache.get_children(folder_id)
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

    def go_up(self):
        if self.current_folder_id in ["my_drive", "shared_with_me"] or not self.gcache:
            return
            
        current_item = self.gcache.get_item(self.current_folder_id)
        if not current_item:
            return
            
        parent_id = current_item.get('parent_id')
        if not parent_id:
            # Shared with me root items have parent_id IS NULL in gcache
            self.load_root("shared_with_me", highlight_fileid=self.current_folder_id)
            return

        if len(parent_id) == 19:
            # My Drive root items have parent_id length 19 in gcache
            self.load_root("my_drive", highlight_fileid=self.current_folder_id)
            return

        parent_item = self.gcache.get_item(parent_id)
        if parent_item:
            self.load_folder(parent_id, parent_item['name'], highlight_fileid=self.current_folder_id)

    def update_nav_buttons(self):
        self.back_btn.setEnabled(self.history_index > 0)
        self.fwd_btn.setEnabled(self.history_index < len(self.history) - 1)
        self.up_btn.setEnabled(self.current_folder_id not in ["my_drive", "shared_with_me"])

    def on_nav_clicked(self, item: QListWidgetItem):
        root_type = item.data(Qt.ItemDataRole.UserRole)
        self.load_root(root_type)

    def on_address_bar_return(self):
        if not self.gcache:
            QMessageBox.information(self, "Loading", "Please wait for the cache to finish loading.")
            return

        query = self.address_bar.text()
        if not query:
            return
        
        import gdrive
        try:
            # resulting_tuple is (public_folder, private_folder)
            resulting_tuple = gdrive.get_gfolders_for_course(query, invite_to_add=False)
            folder_id = resulting_tuple[1] or resulting_tuple[0]
            if not folder_id:
                return
            
            # Use gcache to get the folder's name
            folder_item = self.gcache.get_item(folder_id)
            if folder_item:
                folder_name = folder_item.get('name', query)
            else:
                folder_name = query
                
            self.load_folder(folder_id, folder_name)
        except FileNotFoundError as e:
            QMessageBox.warning(self, "Not Found", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def update_completer(self, text):
        if not text or not self.gcache:
            return
        import gdrive
        suggestions = gdrive.get_course_suggestions(text)
        self.completer_model.setStringList(suggestions)

    def populate_files(self, items: List[Dict[str, Any]]):
        if not self.gcache:
            return
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
                pixmap = cached_pixmap
            else:
                pixmap = get_mime_icon(mime).pixmap(self.file_view.iconSize())
            
            cache_path = self.gcache.get_cache_path_for_file(item)
            if cache_path:
                if cache_path.exists():
                    pixmap = self.apply_icon_overlay(pixmap, FilledIcon.CIRCLE_CHECK)
            elif item.get('mimeType') not in ('application/vnd.google-apps.folder', 'application/vnd.google-apps.shortcut'):
                pixmap = self.apply_icon_overlay(pixmap, OutlineIcon.EXTERNAL_LINK)
            
            list_item.setIcon(QIcon(pixmap))
            
            if not cached_pixmap and (mime == 'application/pdf' or mime.startswith('video/')):
                items_needing_thumbnails.append(item)
            
            list_item.setData(Qt.ItemDataRole.UserRole, item)
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
            file_data = item.data(Qt.ItemDataRole.UserRole)
            mime = file_data.get('mimeType', '')
            file_id = file_data.get('id', '')
            
            if (mime == 'application/pdf' or mime.startswith('video/')) and file_id not in self.queued_thumbnails:
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
        # Ensure the image is padded to the full icon size to prevent label shifting
        # and ensure the previous render is fully cleared.
        target_size = self.file_view.iconSize().width()
        if not img.isNull() and (img.width() != target_size or img.height() != target_size):
            padded = QImage(target_size, target_size, QImage.Format.Format_ARGB32)
            padded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(padded)
            # Center the image
            x = (target_size - img.width()) // 2
            y = (target_size - img.height()) // 2
            painter.drawImage(x, y, img)
            painter.end()
            img = padded

        pixmap = QPixmap.fromImage(img)
        self.thumbnail_cache.put(file_id, pixmap)
        if file_id in self.item_mapping:
            item = self.item_mapping[file_id]
            if item.listWidget() == self.file_view:
                file_data = item.data(Qt.ItemDataRole.UserRole)
                assert self.gcache
                cache_path = self.gcache.get_cache_path_for_file(file_data)
                if cache_path:
                    if cache_path.exists():
                        pixmap = self.apply_icon_overlay(pixmap, FilledIcon.CIRCLE_CHECK)
                elif file_data.get('mimeType') not in ('application/vnd.google-apps.folder', 'application/vnd.google-apps.shortcut'):
                    pixmap = self.apply_icon_overlay(pixmap, OutlineIcon.EXTERNAL_LINK)
                item.setIcon(QIcon(pixmap))

    def show_file_view_context_menu(self):
        if self.file_view.hasFocus():
            item = self.file_view.currentItem()
            if item:
                # visualItemRect returns rect in viewport coordinates
                rect = self.file_view.visualItemRect(item)
                self.on_context_menu(rect.center())

    def on_context_menu(self, pos):
        item = self.file_view.itemAt(pos)
        if not item:
            return
            
        file_data = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        # The & below marks which letter is the hotkey for that option
        copy_id_action = menu.addAction("Copy &ID")
        copy_link_action = menu.addAction("Copy &URL")
        open_browser_action = menu.addAction("&Open in browser...")
        rename_action = menu.addAction("&Rename...")
        move_file_action = menu.addAction("&Move file...")
        
        action = menu.exec(self.file_view.viewport().mapToGlobal(pos))
        url = gdrive_base.GENERIC_LINK_PREFIX + file_data['id']
        if action == copy_id_action:
            QApplication.clipboard().setText(file_data['id'])
        elif action == copy_link_action:
            QApplication.clipboard().setText(url)
        elif action == open_browser_action:
            webbrowser.open(url)
        elif action == rename_action:
            self.rename_file(file_data)
        elif action == move_file_action:
            self.move_file(file_data)

    def trigger_rename(self):
        if self.file_view.hasFocus():
            item = self.file_view.currentItem()
            if item:
                file_data = item.data(Qt.ItemDataRole.UserRole)
                self.rename_file(file_data)

    def rename_file(self, file_data: Dict[str, Any]):
        new_name, ok = QInputDialog.getText(
            self, "Rename", "Enter new name:",
            text=file_data['name']
        )
        if ok and new_name and new_name != file_data['name']:
            try:
                # Use a progress dialog for the rename operation as it can be slow
                progress = QProgressDialog("Renaming...", "Cancel", 0, 0, self)
                progress.setWindowTitle("Renaming")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
                QApplication.processEvents()
                
                assert self.gcache
                self.gcache.rename_file(file_data['id'], new_name)
                
                progress.close()
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename file: {e}")

    def move_file(self, file_data: dict[str, Any]):
        dialog = MoveFileDialog(self, self.gcache)
        if dialog.exec():
            try:
                import gdrive
                # Use a progress dialog for the move operation as it can be slow
                progress = QProgressDialog("Moving file...", "Cancel", 0, 0, self)
                progress.setWindowTitle("Moving")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.show()
                QApplication.processEvents()
                
                gdrive.move_gfile(file_data['id'], dialog.resulting_tuple)
                
                progress.close()
                
                self.refresh()
                    
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to move file: {e}")

    def refresh(self):
        """Reloads the current folder (to pick up file changes)"""
        if self.current_folder_id in ["my_drive", "shared_with_me"]:
            self.load_root(self.current_folder_id, add_history=False)
        else:
            assert self.current_folder_id
            self.load_folder(self.current_folder_id, self.address_bar.text(), add_history=False)

    def on_item_activated(self, item: QListWidgetItem):
        assert self.gcache
        file_data = item.data(Qt.ItemDataRole.UserRole)
        mime = file_data.get('mimeType', '')
        
        if mime == 'application/vnd.google-apps.folder':
            self.load_folder(file_data['id'], file_data['name'], clicked_item_id=file_data['id'])
        elif mime == 'application/vnd.google-apps.shortcut':
            if file_data['shortcutDetails']['targetMimeType'] == 'application/vnd.google-apps.folder':
                folder_id = file_data['shortcutDetails']['targetId']
                target_file = None
            else:
                target_file = self.gcache.get_item(file_data['shortcutDetails']['targetId'])
                folder_id = target_file['parent_id']
                target_file = target_file['id']
            target_folder = self.gcache.get_item(folder_id)
            if not target_folder:
                url = gdrive_base.FOLDER_LINK.format(folder_id)
                webbrowser.open(url)
            self.load_folder(target_folder['id'], target_folder['name'], highlight_fileid=target_file, clicked_item_id=file_data['id'])
        else:
            self.open_file(file_data)

    def open_file(self, file_data: Dict[str, Any]):
        assert self.gcache
        cache_path = self.gcache.get_cache_path_for_file(file_data)
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
        if event.key() == Qt.Key.Key_Backspace:
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
