import sys
import os
import json
import subprocess
import webbrowser
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QListWidget, QListWidgetItem,
                               QPushButton, QLineEdit, QSplitter, QMessageBox,
                               QListView, QMenu, QProgressDialog, QCompleter,
                               QDialog, QLabel, QInputDialog, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView,
                               QDialogButtonBox, QFrame)
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QPixmap, QShortcut, QKeySequence, QFont

import pytablericons
from pytablericons.outline_icon import OutlineIcon
from pytablericons.filled_icon import FilledIcon


from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt, QRunnable, Signal, QThreadPool, Slot, QTimer, QThread, QStringListModel, QObject
from PySide6.QtGui import QPainter, QImage, QPen

from collections import OrderedDict
from functools import lru_cache
import pdfutils
import videoutils
import gdrive_base
from strutils import thumbnail_path_for_file, THUMBNAIL_SIZES, format_size
from local_gdrive import DriveCache


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

class GDriveActionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class GDriveActionSignals(QObject):
    # Signal can only take simple types, so we can't use `set[str]`
    finished = Signal(set) # the impacted folder ids
    error = Signal(str) # the error message
    started = Signal()
    status_changed = Signal()

class GDriveAction(QRunnable):
    def __init__(self, description: str):
        super().__init__()
        self.signals = GDriveActionSignals()
        self.impacted_folders: set[str] = set()
        self.description = description
        self.status = GDriveActionStatus.PENDING
        self.error_message = None

    @Slot()
    def run(self):
        self.status = GDriveActionStatus.RUNNING
        self.signals.started.emit()
        self.signals.status_changed.emit()
        try:
            self.execute()
            self.status = GDriveActionStatus.COMPLETED
            self.signals.finished.emit(self.impacted_folders)
            self.signals.status_changed.emit()
        except Exception as e:
            self.status = GDriveActionStatus.ERROR
            self.error_message = str(e)
            self.signals.error.emit(str(e))
            self.signals.status_changed.emit()

    def execute(self):
        raise NotImplementedError

class RenameAction(GDriveAction):
    def __init__(self, gcache: DriveCache, file_id: str, new_name: str):
        item = gcache.get_item(file_id)
        old_name = item['name'] if item else file_id
        super().__init__(f"Renaming '{old_name}' to '{new_name}'")
        self.gcache = gcache
        self.file_id = file_id
        self.new_name = new_name
        
        if item:
            if item.get('parent_id'):
                self.impacted_folders.add(item['parent_id'])
            if item.get('mimeType') == 'application/vnd.google-apps.folder':
                self.impacted_folders.add(file_id)

    def execute(self):
        self.gcache.rename_file(self.file_id, self.new_name)
        self.description = self.description.replace("Renaming ", "Renamed ")

class MoveAction(GDriveAction):
    def __init__(self, gcache: DriveCache, file_id: str, destination: str | tuple[str | None, str | None], previous_parents: list[str] | None = None):
        item = gcache.get_item(file_id)
        name = item['name'] if item else file_id
        
        dest_name = "folder"
        if isinstance(destination, str):
            dest_item = gcache.get_item(destination)
            if dest_item:
                dest_name = f"'{dest_item['name']}'"
        elif isinstance(destination, tuple):
            dest_name = "selected folder"

        super().__init__(f"Moving '{name}' to {dest_name}")
        self.gcache = gcache
        self.file_id = file_id
        self.destination = destination
        self.previous_parents = previous_parents

        if previous_parents:
            self.impacted_folders.update(previous_parents)
        else:
            if item and item.get('parent_id'):
                self.impacted_folders.add(item['parent_id'])
                
        if isinstance(destination, tuple):
            if destination[0]: self.impacted_folders.add(destination[0])
            if destination[1]: self.impacted_folders.add(destination[1])
        else:
            self.impacted_folders.add(destination)

    def execute(self):
        if isinstance(self.destination, tuple):
            import gdrive
            gdrive.move_gfile(self.file_id, self.destination)
        else:
            self.gcache.move_file(self.file_id, self.destination, previous_parents=self.previous_parents)
        self.description = self.description.replace("Moving ", "Moved ")

class CreateFolderAction(GDriveAction):
    def __init__(self, gcache: DriveCache, parent_id: str, folder_name: str):
        super().__init__(f"Creating folder '{folder_name}'")
        self.gcache = gcache
        self.parent_id = parent_id
        self.folder_name = folder_name
        self.impacted_folders.add(parent_id)

    def execute(self):
        self.gcache.create_folder(folder_name=self.folder_name, parent_id=self.parent_id)
        self.description = self.description.replace("Creating ", "Created ")

class DownloadAction(GDriveAction):
    def __init__(self, gcache: DriveCache, file_data: Dict[str, Any]):
        super().__init__(f"Downloading '{file_data['name']}'")
        self.gcache = gcache
        self.file_data = file_data
        self.impacted_folders.add(file_data['parent_id'])

    def execute(self):
        self.gcache.download_file_to_cache(self.file_data)
        self.description = self.description.replace("Downloading ", "Downloaded ")

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
        self.resulting_tuple: tuple[str | None, str | None] | None = None
        
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

class FileListWidget(QListWidget):
    itemDropped = Signal(object, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QListView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.hovered_item = None
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self._auto_scroll)
        self.scroll_direction = 0
        self.scroll_speed = 0

    def _auto_scroll(self):
        sb = self.verticalScrollBar()
        sb.setValue(sb.value() + self.scroll_direction * self.scroll_speed)
        
    def dragEnterEvent(self, event):
        super().dragEnterEvent(event)
        if event.source() == self:
            event.accept()

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        
        outer_margin = 60
        inner_margin = 20
        y = event.pos().y()
        height = self.viewport().height()
        
        if y < outer_margin:
            self.scroll_direction = -1
            self.scroll_speed = 75 if y < inner_margin else 25
            if not self.scroll_timer.isActive():
                self.scroll_timer.start(50)
        elif y > height - outer_margin:
            self.scroll_direction = 1
            self.scroll_speed = 75 if y > height - inner_margin else 25
            if not self.scroll_timer.isActive():
                self.scroll_timer.start(50)
        else:
            self.scroll_timer.stop()

        if event.source() == self:
            target_item = self.itemAt(event.pos())
            if target_item != self.hovered_item:
                if self.hovered_item:
                    self._restore_icon(self.hovered_item)
                
                if target_item:
                    target_data = target_item.data(Qt.ItemDataRole.UserRole)
                    if target_data.get('mimeType', '') == 'application/vnd.google-apps.folder':
                        self.hovered_item = target_item
                        self._set_open_folder_icon(target_item)
                    else:
                        self.hovered_item = None
                else:
                    self.hovered_item = None
            
            if target_item:
                target_data = target_item.data(Qt.ItemDataRole.UserRole)
                mime = target_data.get('mimeType', '')
                if mime == 'application/vnd.google-apps.folder':
                    event.accept()
                    return
            event.ignore()

    def dragLeaveEvent(self, event):
        self.scroll_timer.stop()
        if self.hovered_item:
            self._restore_icon(self.hovered_item)
            self.hovered_item = None
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.scroll_timer.stop()
        if self.hovered_item:
            self._restore_icon(self.hovered_item)
            self.hovered_item = None
            
        if event.source() == self:
            target_item = self.itemAt(event.pos())
            if target_item:
                target_data = target_item.data(Qt.ItemDataRole.UserRole)
                mime = target_data.get('mimeType', '')
                if mime == 'application/vnd.google-apps.folder':
                    source_items = self.selectedItems()
                    if not source_items and self.currentItem():
                        source_items = [self.currentItem()]
                    source_items = [item for item in source_items if item != target_item]
                    if source_items:
                        source_datas = [item.data(Qt.ItemDataRole.UserRole) for item in source_items]
                        self.itemDropped.emit(source_datas, target_data)
                        # Set action to CopyAction to prevent QListWidget from 
                        # optimistically removing the item before we refresh.
                        event.setDropAction(Qt.DropAction.CopyAction)
                        event.accept()
                        return
        super().dropEvent(event)

    def _set_open_folder_icon(self, item):
        self.original_icon = item.icon()
        color = QApplication.palette().windowText().color().name()
        item.setIcon(get_icon(OutlineIcon.FOLDER_OPEN, color=color))
        
    def _restore_icon(self, item):
        if hasattr(self, 'original_icon') and self.original_icon is not None:
            item.setIcon(self.original_icon)
            self.original_icon = None

class PieProgressBar(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self._value = 0
        self._maximum = 1
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def setValue(self, value):
        self._value = value
        self.update()
        
    def setMaximum(self, maximum):
        self._maximum = maximum
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(2, 2, -2, -2)
        
        # Draw background circle
        bg_color = QApplication.palette().alternateBase().color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawEllipse(rect)
        
        # Draw pie
        if self._maximum > 0:
            fg_color = QApplication.palette().highlight().color()
            painter.setBrush(fg_color)
            
            start_angle = 90 * 16
            progress = self._value / self._maximum
            span_angle = int(-progress * 360 * 16)
            
            painter.drawPie(rect, start_angle, span_angle)
            
            # Draw a subtle outline
            outline_pen = QPen(QApplication.palette().text().color(), 1)
            c = outline_pen.color()
            c.setAlpha(64)
            outline_pen.setColor(c)
            painter.setPen(outline_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)

class SpinningIconLabel(QLabel):
    def __init__(self, icon_enum, color: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.icon_enum = icon_enum
        self.color = color
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.start(30) # ~33 fps
        self.setFixedSize(24, 24)
        
        # We need the pixmap to rotate
        icon = get_icon(self.icon_enum, color=self.color)
        self._pixmap = icon.pixmap(48, 48) # Render larger then scale down for better quality

    def _rotate(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Center the painter
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        
        # Draw the pixmap centered
        painter.drawPixmap(-12, -12, 24, 24, self._pixmap)

class GDriveProgressPopover(QDialog):
    def __init__(self, parent, gdrive_actions: list[GDriveAction]):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.gdrive_actions = gdrive_actions
        self.setMinimumWidth(350)
        self.setMaximumHeight(400)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1) # Small border
        
        self.container = QWidget()
        self.container.setObjectName("popoverContainer")
        self.container.setStyleSheet("""
            QWidget#popoverContainer {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        
        header = QHBoxLayout()
        title = QLabel("Google Drive Operations")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin: 5px;")
        header.addWidget(title)
        header.addStretch()
        
        clear_btn = QPushButton("Clear Completed")
        clear_btn.setStyleSheet("font-size: 11px;")
        clear_btn.clicked.connect(self.clear_completed)
        header.addWidget(clear_btn)
        
        container_layout.addLayout(header)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                border-bottom: 1px solid palette(alternate-base);
            }
        """)
        container_layout.addWidget(self.list_widget)
        
        layout.addWidget(self.container)
        
        self.refresh_list()

    def clear_completed(self):
        # We need to notify the parent to actually clear them from the list
        parent = self.parent()
        assert isinstance(parent, GDriveApp)
        parent.clear_completed_actions()
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        if not self.gdrive_actions:
            item = QListWidgetItem("No active operations")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            return

        # Show most recent first
        for action in reversed(self.gdrive_actions):
            item = QListWidgetItem()
            widget = QWidget()
            item_layout = QHBoxLayout(widget)
            item_layout.setContentsMargins(8, 8, 8, 8)
            
            status_color = None
            if action.status == GDriveActionStatus.RUNNING:
                icon_label = SpinningIconLabel(OutlineIcon.LOADER_2)
            else:
                icon_label = QLabel()
                icon_label.setFixedSize(24, 24)
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if action.status == GDriveActionStatus.PENDING:
                    icon = get_icon(OutlineIcon.CLOCK)
                elif action.status == GDriveActionStatus.COMPLETED:
                    icon = get_icon(OutlineIcon.CIRCLE_CHECK, color="#28a745")
                    status_color = "#28a745"
                elif action.status == GDriveActionStatus.ERROR:
                    icon = get_icon(OutlineIcon.CIRCLE_X, color="#dc3545")
                    status_color = "#dc3545"
                else:
                    icon = get_icon(OutlineIcon.QUESTION_MARK)
                
                icon_label.setPixmap(icon.pixmap(24, 24))
            
            item_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
            
            text_layout = QVBoxLayout()
            desc_label = QLabel(action.description)
            desc_label.setWordWrap(True)
            text_layout.addWidget(desc_label)
            
            status_text = action.status.capitalize()
            status_label = QLabel(status_text)
            status_label.setStyleSheet(f"font-size: 10px; color: {status_color if status_color else 'palette(text)'};")
            text_layout.addWidget(status_label)
            
            if action.status == GDriveActionStatus.ERROR and action.error_message:
                error_label = QLabel(action.error_message)
                error_label.setStyleSheet("color: #dc3545; font-size: 9px;")
                error_label.setWordWrap(True)
                text_layout.addWidget(error_label)
            
            item_layout.addLayout(text_layout, 1)
            
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

class ClickSelectLineEdit(QLineEdit):
    escPressed = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.hasFocus():
            self.setFocus()
            self.selectAll()
        else:
            super().mousePressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Use QTimer.singleShot to ensure selectAll happens after 
        # any other focus-related event processing.
        QTimer.singleShot(0, self.selectAll)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.escPressed.emit()
        else:
            super().keyPressEvent(event)

class GDriveApp(QMainWindow):
    thumbnail_loaded_signal = Signal(str, QImage)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Google Drive Explorer")
        self.resize(1000, 600)
        
        self.history: List[HistoryEntry] = []
        self.history_index = -1
        self.current_folder_id: str | None = None
        
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(10)
        self.thumbnail_cache = LRUCache(500)
        self.item_mapping: Dict[str, QListWidgetItem] = {}
        self.current_cancel_flag = [False]
        self.queued_thumbnails = set()
        self.thumbnail_loaded_signal.connect(self.on_thumbnail_loaded)
        
        self.gdrive_pool = QThreadPool(self)
        self.gdrive_pool.setMaxThreadCount(10)
        self.gdrive_tasks_total = 0
        self.gdrive_tasks_completed = 0
        self.gdrive_actions: list[GDriveAction] = []
        self.progress_popover = None
        self.is_search_mode = False
        
        self.gcache: DriveCache | None = None
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
        
        self.address_bar = ClickSelectLineEdit()
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
        
        self.search_btn = QPushButton()
        self.search_btn.setIcon(get_icon(OutlineIcon.SEARCH))
        self.search_btn.setToolTip("Search (Ctrl+K)")
        self.search_btn.setCheckable(True)
        self.search_btn.toggled.connect(self.toggle_search_mode)
        top_bar.addWidget(self.search_btn)
        
        self.gdrive_progress_widget = PieProgressBar()
        self.gdrive_progress_widget.clicked.connect(self.toggle_progress_popover)
        top_bar.addWidget(self.gdrive_progress_widget)
        
        self.folder_menu_btn = QPushButton()
        self.folder_menu_btn.setIcon(get_icon(OutlineIcon.DOTS))
        self.folder_menu_btn.setToolTip("Folder actions")
        self.folder_menu_btn.clicked.connect(self.on_folder_context_menu)
        top_bar.addWidget(self.folder_menu_btn)
        
        right_layout.addLayout(top_bar)
        
        # Main File View
        self.file_view = FileListWidget()
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
        self.file_view.itemDropped.connect(self.on_item_dropped)
        self.address_bar.escPressed.connect(self.on_address_bar_esc)
        
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

        # Shortcuts for exiting
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.quit_shortcut.activated.connect(self.close)
        self.close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self.close_shortcut.activated.connect(self.close)

        # Shortcuts for address bar
        self.focus_address_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self.focus_address_shortcut.activated.connect(self.address_bar.setFocus)
        self.focus_address_alt_shortcut = QShortcut(QKeySequence("Alt+D"), self)
        self.focus_address_alt_shortcut.activated.connect(self.address_bar.setFocus)
        
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.search_shortcut.activated.connect(self.on_search_shortcut)
        
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
        if not self.current_folder_id or self.current_folder_id in ["my_drive", "shared_with_me"] or not self.gcache:
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
        is_root = self.current_folder_id in ["my_drive", "shared_with_me"]
        self.up_btn.setEnabled(not is_root)
        self.folder_menu_btn.setEnabled(not is_root)

    def on_nav_clicked(self, item: QListWidgetItem):
        root_type = item.data(Qt.ItemDataRole.UserRole)
        self.load_root(root_type)

    def on_address_bar_esc(self):
        if getattr(self, 'is_search_mode', False):
            self.search_btn.setChecked(False)
        self.file_view.setFocus()

    def on_search_shortcut(self):
        if not self.search_btn.isChecked():
            self.search_btn.setChecked(True)
        else:
            self.address_bar.setFocus()
            self.address_bar.selectAll()

    def toggle_search_mode(self, checked):
        self.is_search_mode = checked
        if checked:
            self.address_bar.setPlaceholderText("Search files & folders...")
            self.address_bar.setText("")
            self.address_bar.setFocus()
            self.completer_model.setStringList([])
        else:
            self.address_bar.setPlaceholderText("")
            self.address_bar.setText(self.history[self.history_index].name if self.history_index >= 0 else "")
            self.completer_model.setStringList([])

    def go_to_search_result(self, file_data):
        file_id = file_data['id']
        if file_data['mimeType'] == 'application/vnd.google-apps.folder':
            self.load_folder(file_id, file_data['name'], add_history=True)
            return
        
        parent_id = file_data.get('parents', [None])[0]
        if not parent_id:
            owners = file_data.get('owners', [{}])
            if owners and owners[0].get('me'):
                self.load_root("my_drive", add_history=True, highlight_fileid=file_id)
            else:
                self.load_root("shared_with_me", add_history=True, highlight_fileid=file_id)
            return
            
        if len(parent_id) == 19:
            self.load_root("my_drive", add_history=True, highlight_fileid=file_id)
            return
            
        assert self.gcache
        parent = self.gcache.get_item(parent_id)
        if parent:
            self.load_folder(parent['id'], parent['name'], add_history=True, highlight_fileid=file_id)

    def on_address_bar_return(self):
        if not self.gcache:
            QMessageBox.information(self, "Loading", "Please wait for the cache to finish loading.")
            return

        query = self.address_bar.text()
        if not query:
            return

        if getattr(self, 'is_search_mode', False):
            if hasattr(self, 'search_results_map') and query in self.search_results_map:
                file_data = self.search_results_map[query]
                self.go_to_search_result(file_data)
                self.search_btn.setChecked(False)
            return

        file_id = gdrive_base.link_to_id(query)
        if file_id:
            file_data = self.gcache.get_item(file_id)
            if not file_data:
                QMessageBox.warning(self, "File not found", f"The file with id {file_id} was not found in the cache.")
                return
            if file_data['mimeType'] == 'application/vnd.google-apps.folder':
                self.load_folder(file_id, file_data['name'], add_history=True)
                return
            parent = self.gcache.get_item(file_data['parent_id'])
            if not parent:
                assert not file_data['owners'][0]['me']
                self.load_root("shared_with_me", highlight_fileid=file_id)
                return
            if len(parent['id']) == 19:
                self.load_root("my_drive", add_history=True, highlight_fileid=file_id)
                return
            self.load_folder(parent['id'], parent['name'], add_history=True, highlight_fileid=file_id)
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
        if getattr(self, 'is_search_mode', False):
            results = self.gcache.search_by_name_containing(text, limit=20)
            self.search_results_map = {}
            for res in results:
                name = res['name']
                if name in self.search_results_map:
                    name = f"{name} ({res['id'][:6]})"
                self.search_results_map[name] = res
            self.completer_model.setStringList(list(self.search_results_map.keys()))
        else:
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
                    item['_cache_status'] = 'cached'
                else:
                    item['_cache_status'] = 'uncached'
                    pixmap = self.apply_icon_overlay(pixmap, OutlineIcon.CLOUD)
            else:
                item['_cache_status'] = 'uncacheable'
                if item.get('mimeType') not in ('application/vnd.google-apps.folder', 'application/vnd.google-apps.shortcut'):
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
            self.on_folder_context_menu(self.file_view.viewport().mapToGlobal(pos), inside=True)
            return
            
        selected_items = self.file_view.selectedItems()
        if len(selected_items) > 1 and item in selected_items:
            file_datas = [si.data(Qt.ItemDataRole.UserRole) for si in selected_items]
        else:
            file_datas = [item.data(Qt.ItemDataRole.UserRole)]
            
        self.show_gdrive_context_menu(file_datas, self.file_view.viewport().mapToGlobal(pos))

    def on_folder_context_menu(self, global_pos: Optional[QPoint] = None, inside=False):
        if not self.current_folder_id or not self.gcache or self.current_folder_id in ["my_drive", "shared_with_me"]:
            return
            
        folder_data = self.gcache.get_item(self.current_folder_id)
        if not folder_data:
            return
            
        if not isinstance(global_pos, QPoint):
            global_pos = self.folder_menu_btn.mapToGlobal(self.folder_menu_btn.rect().bottomLeft())
            
        self.show_gdrive_context_menu([folder_data], global_pos, hide_edit_options=inside, add_options=True)

    def show_gdrive_context_menu(self, file_datas: List[Dict[str, Any]], global_pos: QPoint, hide_edit_options: bool = False, add_options: bool = False):
        if not file_datas:
            return
            
        menu = QMenu(self)
        if len(file_datas) > 1:
            copy_ids_action = menu.addAction("Copy &IDs")
            move_action = menu.addAction("&Move files...")
            
            action = menu.exec(global_pos)
            if action == copy_ids_action:
                QApplication.clipboard().setText(json.dumps([f['id'] for f in file_datas]))
            elif action == move_action:
                self.move_files(file_datas)
            return

        # Single item
        file_data = file_datas[0]
        is_folder = file_data.get('mimeType') == 'application/vnd.google-apps.folder'
        move_label = "&Move folder..." if is_folder else "&Move file..."
        
        info_action = menu.addAction("Info...")
        copy_id_action = menu.addAction("Copy ID")
        copy_link_action = menu.addAction("Copy &URL")
        open_browser_action = menu.addAction("&Open in browser...")
        if not hide_edit_options:
            rename_action = menu.addAction("&Rename...")
            move_action = menu.addAction(move_label)
        else:
            rename_action = None
            move_action = None
        if not is_folder:
            if file_data.get('_cache_status') == 'uncached':
                download_action = menu.addAction("&Download to cache")
            else:
                download_action = None
            if file_data.get('_cache_status') == 'cached':
                uncache_action = menu.addAction("Remove from cache")
            else:
                uncache_action = None
        else:
            download_action = None
            uncache_action = None
        if is_folder and add_options:
            new_folder_action = menu.addAction("New &Folder...")
        else:
            new_folder_action = None
        
        action = menu.exec(global_pos)
        if not action:
            return
            
        url = gdrive_base.GENERIC_LINK_PREFIX + file_data['id']
        if action == copy_id_action:
            QApplication.clipboard().setText(file_data['id'])
        elif action == info_action:
            self.info_dialog_for_file(file_data)
        elif action == copy_link_action:
            QApplication.clipboard().setText(url)
        elif action == open_browser_action:
            webbrowser.open(url)
        elif action == rename_action:
            self.rename_file(file_data)
        elif action == move_action:
            self.move_files([file_data])
        elif action == new_folder_action:
            self.new_folder(file_data)
        elif action == download_action:
            assert self.gcache
            self.queue_gdrive_action(DownloadAction(self.gcache, file_data))
        elif action == uncache_action:
            assert self.gcache
            cache_path = self.gcache.get_cache_path_for_file(file_data)
            if cache_path and cache_path.exists():
                if cache_path.stat().st_size > 50000000:
                    size_mb = cache_path.stat().st_size / 1024 / 1024
                    reply = QMessageBox.question(
                        self, "Confirm Delete",
                        f"This file is {size_mb:.1f} MB. Are you sure you want to remove it from the cache?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                cache_path.unlink()
                self.refresh()
    def info_dialog_for_file(self, file_data: Dict):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"File Information - {file_data.get('name', 'Unknown')}")
        dialog.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_label = QLabel(f"<b>{file_data.get('name', 'Unknown')}</b>")
        title_label.setStyleSheet("font-size: 16pt;")
        layout.addWidget(title_label)
        
        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Property", "Value"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setFrameStyle(QFrame.Shape.NoFrame)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Make the table look "pretty"
        table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                alternate-background-color: rgba(0, 0, 0, 0.05);
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: transparent;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #ccc;
                padding: 4px;
            }
        """)

        def add_row(key, value, raw_value=None):
            if value is None: return
            row = table.rowCount()
            table.insertRow(row)
            
            key_item = QTableWidgetItem(str(key))
            key_item.setFont(QFont("", -1, QFont.Weight.Bold))
            table.setItem(row, 0, key_item)
            
            val_item = QTableWidgetItem(str(value))
            val_item.setToolTip(str(value))
            if raw_value is not None:
                val_item.setData(Qt.ItemDataRole.UserRole, raw_value)
            table.setItem(row, 1, val_item)

        add_row("Name", file_data.get('name'))
        add_row("ID", file_data.get('id'))
        add_row("MIME Type", file_data.get('mimeType'))
        
        size = file_data.get('size')
        if size is not None and file_data.get('mimeType') != 'application/vnd.google-apps.folder':
            add_row("Size", format_size(int(size)), raw_value=size)
            
        add_row("Modified", file_data.get('modifiedTime'))
        
        if file_data.get('md5Checksum'):
            add_row("MD5 Checksum", file_data['md5Checksum'])
            
        # Parent Info
        parent_id = file_data.get('parent_id')
        if parent_id:
            parent_item = self.gcache.get_item(parent_id) if self.gcache else None
            if parent_item:
                add_row("Parent Folder", f"{parent_item['name']} ({parent_id})")
            else:
                add_row("Parent ID", parent_id)
        
        # Owners
        owners = file_data.get('owners', [])
        if owners:
            owner_strs = [f"{o.get('displayName')} <{o.get('email')}>" for o in owners]
            add_row("Owners", ", ".join(owner_strs))
            
        # Cache Status
        if self.gcache:
            cache_path = self.gcache.get_cache_path_for_file(file_data)
            if cache_path:
                status = "Cached" if cache_path.exists() else "Not Cached"
                add_row("Cache Status", status)
                if cache_path.exists():
                    add_row("Cache Path", str(cache_path))
        
        # Shortcut Details
        shortcut = file_data.get('shortcutDetails')
        if shortcut:
            add_row("Shortcut Target ID", shortcut.get('targetId'))
            add_row("Shortcut Target MIME", shortcut.get('targetMimeType'))
            
        # Properties
        props = file_data.get('properties', {})
        for k, v in props.items():
            add_row(f"Property: {k}", v)
            
        def on_double_click(row, col):
            item = table.item(row, 1)
            if not item: return
            raw = item.data(Qt.ItemDataRole.UserRole)
            QApplication.clipboard().setText(str(raw) if raw is not None else item.text())

        table.cellDoubleClicked.connect(on_double_click)
        table.resizeRowsToContents()
        layout.addWidget(table)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        
        dialog.exec()
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
            assert self.gcache
            action = RenameAction(self.gcache, file_data['id'], new_name)
            self.queue_gdrive_action(action)
    
    def new_folder(self, parent_folder_data: dict[str, Any]):
        new_folder_name, ok = QInputDialog.getText(
            self, "New Folder", "Enter folder name:",
        )
        if ok and new_folder_name:
            assert self.gcache
            action = CreateFolderAction(self.gcache, parent_folder_data['id'], new_folder_name)
            self.queue_gdrive_action(action)

    def move_files(self, file_datas: list[dict[str, Any]]):
        dialog = MoveFileDialog(self, self.gcache)
        assert self.gcache
        if dialog.exec():
            if not dialog.resulting_tuple:
                return
            for file_data in file_datas:
                action = MoveAction(self.gcache, file_data['id'], dialog.resulting_tuple)
                self.queue_gdrive_action(action)

    def on_item_dropped(self, source_datas: list[dict[str, Any]], target_data: dict[str, Any]):
        QTimer.singleShot(0, lambda: self._do_item_dropped(source_datas, target_data))

    def _do_item_dropped(self, source_datas: list[dict[str, Any]], target_data: dict[str, Any]):
        if not self.gcache:
            return
            
        previous_parents = [self.current_folder_id] if self.current_folder_id not in [None, "my_drive", "shared_with_me"] else None
        for source_data in source_datas:
            action = MoveAction(self.gcache, source_data['id'], target_data['id'], previous_parents=previous_parents)
            self.queue_gdrive_action(action)

    def toggle_progress_popover(self):
        if self.progress_popover and self.progress_popover.isVisible():
            self.progress_popover.close()
            return

        if not self.progress_popover:
            self.progress_popover = GDriveProgressPopover(self, self.gdrive_actions)
            
        # Position below the progress widget
        pos = self.gdrive_progress_widget.mapToGlobal(self.gdrive_progress_widget.rect().bottomLeft())
        # Offset to center it a bit better under the widget
        pos.setX(pos.x() - self.progress_popover.minimumWidth() // 2 + self.gdrive_progress_widget.width() // 2)
        # Ensure it doesn't go off screen
        screen_geo = self.screen().geometry()
        if pos.x() + self.progress_popover.width() > screen_geo.right():
            pos.setX(screen_geo.right() - self.progress_popover.width() - 10)
        if pos.x() < screen_geo.left():
            pos.setX(screen_geo.left() + 10)
            
        self.progress_popover.move(pos)
        self.progress_popover.refresh_list()
        self.progress_popover.show()

    def clear_completed_actions(self):
        self.gdrive_actions = [a for a in self.gdrive_actions if a.status not in (GDriveActionStatus.COMPLETED, GDriveActionStatus.ERROR)]
        if self.progress_popover:
            self.progress_popover.gdrive_actions = self.gdrive_actions
        self.gdrive_progress_widget.setMaximum(0)
        self.gdrive_progress_widget.setValue(0)
        self.gdrive_progress_widget.setToolTip("No actions")

    def queue_gdrive_action(self, action: GDriveAction):
        action.signals.finished.connect(self._on_gdrive_action_finished)
        action.signals.error.connect(self._on_gdrive_action_error)
        action.signals.status_changed.connect(self._on_action_status_changed)
        
        self.gdrive_actions.append(action)
        self.gdrive_tasks_total += 1
        self._update_gdrive_progress()
        self.gdrive_pool.start(action)

    def _on_action_status_changed(self):
        if self.progress_popover and self.progress_popover.isVisible():
            self.progress_popover.refresh_list()

    def _update_gdrive_progress(self):
        if self.gdrive_tasks_total > self.gdrive_tasks_completed:
            self.gdrive_progress_widget.setMaximum(self.gdrive_tasks_total)
            self.gdrive_progress_widget.setValue(self.gdrive_tasks_completed)
            self.gdrive_progress_widget.setToolTip(f"Processing... ({self.gdrive_tasks_completed}/{self.gdrive_tasks_total})")
        else:
            self.gdrive_progress_widget.setMaximum(1)
            self.gdrive_progress_widget.setValue(1)
            self.gdrive_progress_widget.setToolTip(f"{self.gdrive_tasks_completed} operations complete!")
            self.gdrive_tasks_total = 0
            self.gdrive_tasks_completed = 0

    def _on_gdrive_action_finished(self, impacted_folders: set[str]):
        self.gdrive_tasks_completed += 1
        if self.current_folder_id in impacted_folders:
            self.refresh()
        self._update_gdrive_progress()

    def _on_gdrive_action_error(self, error_msg):
        self.gdrive_tasks_completed += 1
        self._update_gdrive_progress()
        QMessageBox.critical(self, "Error", f"A Google Drive operation failed: {error_msg}")

    def refresh(self):
        """Reloads the current folder (to pick up file changes)"""
        if not self.current_folder_id:
            return
        if self.current_folder_id in ["my_drive", "shared_with_me"]:
            self.load_root(self.current_folder_id, add_history=False)
        else:
            assert self.gcache
            folder_item = self.gcache.get_item(self.current_folder_id)
            name = folder_item['name'] if folder_item else self.address_bar.text()
            self.load_folder(self.current_folder_id, name, add_history=False)

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
                if not target_file:
                    url = gdrive_base.GENERIC_LINK_PREFIX + (file_data['shortcutDetails']['targetId'] or file_data['id'])
                    webbrowser.open(url)
                    return
                folder_id = target_file['parent_id']
                target_file = target_file['id']
            target_folder = self.gcache.get_item(folder_id)
            if not target_folder:
                url = gdrive_base.FOLDER_LINK.format(folder_id)
                webbrowser.open(url)
                return
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
