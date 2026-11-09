"""Bounded raster tiles presented as independent scene graph textures."""
from collections import OrderedDict
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtQuick import QQuickItem, QSGSimpleTextureNode, QSGTexture

from vocalpitchlab.ui.localization import localized


class RasterLayer(QQuickItem):
    """An immutable image; moving the item never rerasterizes or uploads it."""
    def __init__(self, parent, image, width=None, height=None, source=None):
        super().__init__(parent)
        self.image = image
        self.source = source
        self._texture = None
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.setWidth(image.width()/image.devicePixelRatio() if width is None else width)
        self.setHeight(image.height()/image.devicePixelRatio() if height is None else height)
        self.widthChanged.connect(self.update)
        self.heightChanged.connect(self.update)

    def updatePaintNode(self, node, data):
        if node is None:
            node = QSGSimpleTextureNode()
            self._texture = self.window().createTextureFromImage(self.image)
            node.setTexture(self._texture)
            node.setOwnsTexture(True)
            node.setFiltering(QSGTexture.Filtering.Linear)
        if self.source is not None:
            node.setSourceRect(self.source)
        node.setRect(self.boundingRect())
        return node


class ImageCache:
    def __init__(self, limit=24*1024**2):
        self.limit = limit
        self.images = OrderedDict()
        self.bytes = 0

    def clear(self):
        self.images.clear();self.bytes = 0

    def get(self, key, create):
        if key not in self.images:
            image = create()
            size = image.sizeInBytes()
            if size > self.limit:
                return image
            while self.images and (self.bytes+size > self.limit or len(self.images) >= 32):
                _, old = self.images.popitem(last=False);self.bytes -= old.sizeInBytes()
            self.images[key] = image;self.bytes += size
        self.images.move_to_end(key)
        return self.images[key]


class PlotLayers:
    TILE = 512
    BLEED = 3

    def __init__(self, owner, note_label):
        self.owner = owner
        self.note_label = note_label
        self.active = False
        self.root = QQuickItem(owner);self.root.setClip(True);self.root.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.root.setZ(1)
        self.parts = {}
        self.tiles = {}
        self.highlights = {}
        self.images = ImageCache()
        self.key = self.background_key = None
        self.sources = None
        self.tile_builds = 0
        self.tile_build_ms = []
        self.last_sync_ms = 0.
        self.sync_ms = []
        self.curve_key = None

    @staticmethod
    def retire(item):
        item.setVisible(False);item.setParentItem(None);item.deleteLater()

    def _drop(self, mapping):
        for entry in mapping.values():
            self.retire(entry[-1])
        mapping.clear()

    def hide(self, release=False):
        self.active = False;self.root.setVisible(False)
        for name in ['keyboard', 'readout']:
            if name in self.parts:self.parts[name][-1].setVisible(False)
        if release:
            self._drop(self.tiles);self._drop(self.highlights);self._drop(self.parts)
            self.images.clear();self.key = self.background_key = None;self.sources = None

    def _image(self, width, height, draw):
        image = QImage(max(1,math.ceil(width*self.dpr)),max(1,math.ceil(height*self.dpr)),QImage.Format.Format_ARGB32_Premultiplied)
        if image.isNull():raise MemoryError('Cannot allocate a plot image')
        image.setDevicePixelRatio(self.dpr);image.fill(0)
        painter = QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:draw(painter)
        finally:painter.end()
        return image

    def _part(self, name, key, create, parent=None, x=0., y=0., width=None, height=None):
        parent = self.root if parent is None else parent
        previous = self.parts.get(name)
        if previous is None or previous[0] != key:
            if previous is not None:self.retire(previous[-1])
            item = RasterLayer(parent, create(), width, height)
            self.parts[name] = (key,item)
        else:item = previous[-1]
        item.setVisible(True);item.setPosition(QPointF(x,y))
        if width is not None:item.setWidth(width)
        if height is not None:item.setHeight(height)
        return item

    def _line_image(self, color, width, height):
        def draw(p):
            p.setPen(QPen(QColor(color),width))
            p.drawLine(QPointF(1.5,0),QPointF(1.5,height))
        return self._image(3,height,draw)

    def _tile(self, index, selected=None, top=0., bottom=None):
        b = self.owner._controller
        bottom = self.h if bottom is None else bottom
        lo = (index*self.TILE-self.BLEED)/self.scale
        hi = ((index+1)*self.TILE+self.BLEED)/self.scale
        notes = [n for n in (b.notes if selected is None else selected) if n['end'] >= lo and n['start'] <= hi]
        def draw(p):
            p.translate(self.BLEED-index*self.TILE,-self.y0-top)
            path = QPainterPath()
            if b.show_blocks:
                nh = max(3,min(20,self.h*.64/(b.high-b.low)))
                for n in notes:
                    rect = QRectF(n['start']*self.scale,self.y(n['midi'])-nh/2,max(1.5,(n['end']-n['start'])*self.scale),nh)
                    self.owner.draw_block(p,rect,b.dark,selected is not None)
                    if selected is not None:path.addRect(rect)
            if b.show_curve:
                if selected is not None:
                    if path.isEmpty():return
                    p.setClipPath(path,Qt.ClipOperation.IntersectClip)
                self.owner.draw_detail_curve(p,self.span,self.w,self.h,lo,hi,lambda t:t*self.scale,b.dark)
        start = time.perf_counter()
        image = self._image(self.TILE+2*self.BLEED,bottom-top,draw)
        if selected is None:
            self.tile_builds += 1;self.tile_build_ms.append((time.perf_counter()-start)*1000)
        return image

    def paint_background(self, p):
        b = self.owner._controller
        p.fillRect(self.owner.boundingRect(),QColor('#202226' if b.dark else '#ffffff'))
        p.save();p.setClipRect(QRectF(self.x0,self.y0,self.w,self.h))
        for midi in range(math.floor(b.low),math.ceil(b.high)+1):
            row = QRectF(self.x0,self.y(midi+.5),self.w,self.h/(b.high-b.low))
            if midi%12 in [1,3,6,8,10]:
                p.fillRect(row,QColor('#23262c' if b.dark else '#f7f8fa'))
            if self.row_tint == midi:
                tint = QColor('#6badff' if b.dark else '#0071e3');tint.setAlpha(24 if b.dark else 16);p.fillRect(row,tint)
            p.setPen(QPen(QColor('#2b2e34' if b.dark else '#edf0f3'),.5))
            p.drawLine(QPointF(self.x0,self.y(midi)),QPointF(self.x0+self.w,self.y(midi)))
        p.restore()

    def _keyboard(self, pitches):
        b = self.owner._controller
        def draw(p):
            p.setFont(QFont('Microsoft YaHei',9))
            bg = '#202226' if b.dark else '#ffffff'
            for midi in range(math.floor(b.low),math.ceil(b.high)+1):
                row = QRectF(3,self.y(midi+.5)-self.y0+.5,55,self.h/(b.high-b.low)-1)
                color = ('#29364c' if b.dark else '#eaf0f8') if midi%12 in [1,3,6,8,10] else bg
                p.fillRect(row,QColor(color))
                selected = midi in pitches
                if selected:
                    p.fillRect(QRectF(3,self.y(midi+.5)-self.y0,55,self.h/(b.high-b.low)),QColor('#3c6795' if b.dark else '#d0e5ff'))
                step = max(1,math.ceil((b.high-b.low)*13/self.h))
                if (midi%step==0 or selected) and self.y0+8 <= self.y(midi) <= self.y0+self.h-8:
                    p.setPen(QColor(('#91c6ff' if b.dark else '#0069d2') if selected else ('#9eaec5' if b.dark else '#72809a')))
                    p.drawText(QRectF(3,self.y(midi)-self.y0-9,50,18),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,self.note_label(midi))
        return self._image(58,self.h,draw)

    def _readout(self, labels):
        b = self.owner._controller;box_w = 116*len(labels)
        def draw(p):
            p.translate(1,1)
            p.setPen(QPen(QColor('#4b5665' if b.dark else '#d4dee8'),.8))
            p.setBrush(QColor('#ed29333f' if b.dark else '#f4f4f8fc'));p.drawRoundedRect(QRectF(0,0,box_w,48),14,14)
            for i,(caption,value,detail) in enumerate(labels):
                cx = i*116+12
                font = QFont('Microsoft YaHei');font.setPixelSize(11);p.setFont(font);p.setPen(QColor('#9eaec5' if b.dark else '#72809a'))
                p.drawText(QRectF(cx,5,94,14),Qt.AlignmentFlag.AlignVCenter,caption)
                font.setPixelSize(18);font.setBold(True);p.setFont(font);p.setPen(QColor('#b3d7ff' if b.dark else '#174c82'))
                p.drawText(QRectF(cx,20,52,24),Qt.AlignmentFlag.AlignVCenter,value)
                font.setPixelSize(11);font.setBold(False);p.setFont(font);p.setPen(QColor('#9eaec5' if b.dark else '#72809a'))
                p.drawText(QRectF(cx+50,20,50,24),Qt.AlignmentFlag.AlignVCenter,detail)
                if i:
                    p.setPen(QPen(QColor('#46505c' if b.dark else '#dae2eb'),.7));p.drawLine(QPointF(cx-12,10),QPointF(cx-12,38))
        return self._image(box_w+2,50,draw)

    def sync(self):
        started = time.perf_counter();owner = self.owner;b = owner._controller
        if not b or not b.song or not b.series or owner.window() is None:
            self.hide(release=not b or not b.song);return False
        self.x0,self.y0,self.w,self.h = owner.geometry_values()
        self.dpr = owner.window().devicePixelRatio()
        visible_bytes = (math.ceil(self.w/self.TILE)+1)*(self.TILE+2*self.BLEED)*self.h*self.dpr**2*4
        if visible_bytes > 24*1024**2 or self.h*self.dpr > 8192:
            self.hide();return False
        self.active = True;self.root.setVisible(True)
        self.root.setPosition(QPointF(self.x0,self.y0));self.root.setWidth(self.w);self.root.setHeight(self.h)
        left,right = b.x_range();self.span = min(b.span or b.song['duration'],b.song['duration']);self.scale = self.w/self.span
        self.y = lambda value:self.y0+(b.high-value)/(b.high-b.low)*self.h
        x = lambda t:self.x0+(t-left)*self.scale
        context = owner.interaction_context(left,right,x,self.y,self.x0,self.y0,self.w,self.h)
        times,values = owner.curve_samples(b.primary,self.span,self.w) if b.show_curve else b.series[b.primary]
        reliability = b.curve_reliability.get(b.primary)
        key = (id(b.song),b.song['duration'],id(times),id(values),id(b.notes),id(b.loudness[0]),id(b.loudness[1]),
               id(reliability[0]) if reliability is not None else None,id(reliability[1]) if reliability is not None else None,
               self.span,self.w,self.h,b.low,b.high,self.dpr,b.dark,b.show_blocks,b.show_curve,b.settings.get('cleanCurve',True))
        if key != self.key:
            self._drop(self.tiles);self._drop(self.highlights);self.images.clear();self.key = key
            self.sources = (b.song,times,values,b.notes,b.loudness,reliability)
        self.row_tint = context['key_pitch'] if context['key_notes'] else None
        bg_key = (self.x0,self.y0,self.w,self.h,b.low,b.high,b.dark,self.dpr,self.row_tint)
        if bg_key != self.background_key:
            self.background_key = bg_key;owner.update()
        first = max(0,math.floor(left*self.scale/self.TILE))
        last = min(math.ceil(b.song['duration']*self.scale/self.TILE),math.ceil(right*self.scale/self.TILE))
        visible_tiles = set(range(first,last))
        for index in list(self.tiles):
            if index not in visible_tiles:self.retire(self.tiles.pop(index)[-1])
        builds_before = self.tile_builds
        for index in sorted(visible_tiles):
            if index not in self.tiles:
                image = self.images.get(index,lambda index=index:self._tile(index))
                source = QRectF(self.BLEED*self.dpr,0,self.TILE*self.dpr,self.h*self.dpr)
                item = RasterLayer(self.root,image,self.TILE,self.h,source);item.setZ(2)
                self.tiles[index] = (index,item)
            self.tiles[index][-1].setPosition(QPointF(index*self.TILE-left*self.scale,0))
        if self.tile_builds == builds_before and last*self.TILE < b.song['duration']*self.scale:
            self.images.get(last,lambda:self._tile(last))
        selected = [n for n in context['visible'] if b.show_blocks and
                    (n is context['hovered'] or n is context['active'] or n['midi']==context['key_pitch'])]
        for index in list(self.highlights):
            if index not in visible_tiles:self.retire(self.highlights.pop(index)[-1])
        for index in sorted(visible_tiles):
            chosen = [n for n in selected if n['end']*self.scale >= index*self.TILE-3 and n['start']*self.scale <= (index+1)*self.TILE+3]
            previous = self.highlights.get(index)
            selected_key = tuple(id(n) for n in chosen)
            if not chosen:
                if previous:self.retire(self.highlights.pop(index)[-1])
                continue
            nh = max(3,min(20,self.h*.64/(b.high-b.low)))
            top = max(0,math.floor(min(self.y(n['midi'])-self.y0-nh/2-2 for n in chosen)))
            bottom = min(self.h,math.ceil(max(self.y(n['midi'])-self.y0+nh/2+2 for n in chosen)))
            if bottom <= top:continue
            if previous is None or previous[0] != selected_key:
                if previous:self.retire(previous[-1])
                image = self._tile(index,chosen,top,bottom)
                source = QRectF(self.BLEED*self.dpr,0,self.TILE*self.dpr,(bottom-top)*self.dpr)
                item = RasterLayer(self.root,image,self.TILE,bottom-top,source);item.setZ(3)
                self.highlights[index] = (selected_key,item)
            self.highlights[index][-1].setPosition(QPointF(index*self.TILE-left*self.scale,top))
        pitches = [context['highlighted_pitch']]
        if b.preview_note is not None and time.monotonic() < b.preview_until:pitches.append(b.preview_note)
        self._part('keyboard',(bg_key,tuple(pitches)),lambda:self._keyboard(pitches),owner,0,self.y0).setZ(4)
        self._sync_grid(left,right,bg_key)
        self._sync_loop(b,left,bg_key)
        color = '#60aaff' if b.dark else '#0071e3'
        self._part('cursor',(color,self.h,self.dpr),lambda:self._line_image(color,1.3,self.h),
                   x=(b.t-left)*self.scale-1.5).setZ(7)
        guide = context['hovered'] or (min(context['key_notes'],key=lambda n:n['start']) if context['key_notes'] else None)
        if guide:
            color = QColor('#77b8ff' if b.dark else '#318ce8')
            if context['key_pitch'] is not None:color.setAlpha(100)
            def draw_guide(p):
                pen = QPen(color,.8 if context['key_pitch'] is not None else 1);pen.setStyle(Qt.PenStyle.DashLine);p.setPen(pen)
                p.drawLine(QPointF(0,1.5),QPointF(self.w,1.5))
            item = self._part('guide',(bg_key,color.rgba(),context['key_pitch'] is not None),lambda:self._image(self.w,3,draw_guide),
                              x=0,y=self.y(guide['midi'])-self.y0-1.5)
            item.setZ(4)
            # Clip only the guide's extent; the source image and dash pattern stay fixed.
            item.setWidth(max(0,min(self.w,(guide['start']-left)*self.scale)))
            item.source = QRectF(0,0,item.width()*self.dpr,3*self.dpr)
            item.setClip(True)
        elif 'guide' in self.parts:self.parts['guide'][-1].setVisible(False)
        playback = b.playback;labels = []
        if b.settings['liveNotes']:labels.append((localized(b.settings.get('language'), '主音'),playback['mainNote'],''))
        if b.settings['liveCurve']:
            parts = playback['pitch'].split(' ',1);labels.append((localized(b.settings.get('language'), '曲线'),parts[0],parts[1] if len(parts)>1 else ''))
        if labels:
            width = 116*len(labels);bx = max(self.x0,min(x(b.t)-width/2,self.x0+self.w-width))
            self._part('readout',(tuple(labels),b.dark,self.dpr),lambda:self._readout(labels),owner,bx-1,max(2,self.y0-56)-1).setZ(5)
        elif 'readout' in self.parts:self.parts['readout'][-1].setVisible(False)
        self.last_sync_ms = (time.perf_counter()-started)*1000
        # Bounded diagnostics also used by the repeatable benchmark.
        self.sync_ms.append(self.last_sync_ms)
        if len(self.sync_ms)>2048:del self.sync_ms[:1024]
        if len(self.tile_build_ms)>256:del self.tile_build_ms[:128]
        return True

    def _sync_grid(self,left,right,key):
        b = self.owner._controller
        raw = self.span/8;spacing = 10**math.floor(math.log10(max(raw,.001)))
        spacing *= next(v for v in [1,2,5,10] if v*spacing >= raw)
        ticks = range(math.floor(left/spacing),math.ceil(right/spacing)+1)
        color = '#2b2e34' if b.dark else '#edf0f3'
        for i,tick in enumerate(ticks):
            self._part(f'grid-{i}',(color,self.h,self.dpr),lambda:self._line_image(color,.5,self.h),
                       x=(tick*spacing-left)*self.scale-1.5).setZ(0)
        for name,entry in self.parts.items():
            if name.startswith('grid-') and int(name[5:]) >= len(ticks):entry[-1].setVisible(False)

    def _sync_loop(self,b,left,key):
        if not b.loop:
            for name,entry in self.parts.items():
                if name.startswith('loop-'):entry[-1].setVisible(False)
            return
        def fill(p):p.fillRect(QRectF(0,0,1,1),QColor('#124c97ff'))
        self._part('loop-fill',True,lambda:self._image(1,1,fill),x=(b.loop_a-left)*self.scale,
                   width=(b.loop_b-b.loop_a)*self.scale,height=self.h).setZ(1)
        color = '#6badff' if b.dark else '#0071e3'
        for edge,label in [(b.loop_a,'A'),(b.loop_b,'B')]:
            px = (edge-left)*self.scale
            self._part('loop-line-'+label,(color,self.h,self.dpr),lambda:self._line_image(color,1.3,self.h),x=px-1.5).setZ(5)
            def draw(p,label=label):
                p.setFont(QFont('Microsoft YaHei',9));p.setPen(QPen(QColor(color),1.3));p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(1,1,16,20),4,4);p.setPen(QColor('#101834' if b.dark else '#ffffff'))
                p.drawText(QRectF(1,1,16,20),Qt.AlignmentFlag.AlignCenter,label)
            self._part('loop-cap-'+label,(color,self.dpr,b.dark),lambda:self._image(18,22,draw),x=px-9,y=-1).setZ(6)

    def statistics(self):
        resident = {id(image):image for image in self.images.images.values()}
        for mapping in [self.tiles,self.highlights,self.parts]:
            for entry in mapping.values():
                image = entry[-1].image;resident[id(image)] = image
        return dict(active=self.active,tile_builds=self.tile_builds,cached_tiles=len(self.images.images),
                    allocation_fallback=getattr(self.owner,'layer_allocation_failed',False),
                    cpu_tile_cache_bytes=self.images.bytes,resident_image_bytes=sum(i.sizeInBytes() for i in resident.values()),
                    tile_build_ms=self.tile_build_ms[-256:],sync_ms=self.sync_ms[-2048:])
