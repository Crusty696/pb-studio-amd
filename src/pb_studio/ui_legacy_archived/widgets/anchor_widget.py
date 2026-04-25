"""
Anchor Widget - Few-Shot Learning Anchor-Verwaltung.

Hier kann der User Audio-Bereiche mit Video-Beispielen verknüpfen.
Das System lernt daraus Präferenzen für die automatische Clip-Auswahl.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QHeaderView, QGroupBox
)

logger = logging.getLogger(__name__)


class AnchorWidget(QWidget):
    """Anchor Tab - Few-Shot Learning Verknüpfungen."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        title = QLabel("Anchor System")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        subtitle = QLabel(
            "Verknüpfe Audio-Bereiche mit Video-Beispielen. "
            "Das System lernt daraus deine Vorlieben für ähnliche Musikpassagen."
        )
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        # Stats
        stats_group = QGroupBox("Statistiken")
        stats_layout = QHBoxLayout()
        
        self.anchor_count_label = QLabel("Anchors: 0")
        self.anchor_count_label.setStyleSheet("font-size: 16px;")
        stats_layout.addWidget(self.anchor_count_label)
        
        self.coverage_label = QLabel("Abdeckung: 0.0s")
        self.coverage_label.setStyleSheet("font-size: 16px;")
        stats_layout.addWidget(self.coverage_label)
        
        stats_layout.addStretch()
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Anchor-Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Audio-Bereich", "Video-Clip", "Label", "Similarity"
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("Neuen Anchor erstellen...")
        add_btn.setStyleSheet(
            "QPushButton { padding: 8px 20px; background-color: #007acc; "
            "color: white; border-radius: 4px; }"
        )
        add_btn.clicked.connect(self._on_add_anchor)
        btn_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Ausgewählte entfernen")
        remove_btn.clicked.connect(self._on_remove_anchor)
        btn_layout.addWidget(remove_btn)
        
        clear_btn = QPushButton("Alle löschen")
        clear_btn.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
    
    def _on_add_anchor(self):
        """Platzhalter: Öffnet Dialog zum Anchor-Erstellen."""
        logger.info("Anchor erstellen - Feature wird implementiert wenn Audio-Module portiert sind")
    
    def _on_remove_anchor(self):
        """Platzhalter: Entfernt ausgewählten Anchor."""
        logger.info("Anchor entfernen - noch nicht implementiert")
    
    def _on_clear_all(self):
        """Platzhalter: Löscht alle Anchors."""
        logger.info("Alle Anchors löschen - noch nicht implementiert")
    
    def refresh_view(self):
        """Lädt Anchors aus dem AnchorManager."""
        try:
            from pb_studio.pacing.anchor_manager import get_anchor_manager
            am = get_anchor_manager()
            stats = am.get_stats()
            self.anchor_count_label.setText(f"Anchors: {stats.get('count', 0)}")
            self.coverage_label.setText(f"Abdeckung: {stats.get('total_duration', 0):.1f}s")
        except Exception as e:
            logger.debug(f"Anchor-Stats nicht verfügbar: {e}")
