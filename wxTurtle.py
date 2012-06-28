#!/usr/local/bin/python
# -*- coding: utf-8 -*-
'''wxTurtle
次の課題 png/jpeg 読み込み -> opencv edge 抽出 -> line tracing
http://www.phactory.jp/blog/pyblosxom.cgi/tech/080830.html
Effector
BLUR              ぼかし
CONTOUR           8方向ラプラシアンフィルタ（線画）
DETAIL            細かくエッジを効かせる
EDGE_ENHANCE      輪郭強調
EDGE_ENHANCE_MORE 輪郭強調（強）
EMBOSS            レリーフ
FIND_EDGES        レリーフ
SHARPEN           レリーフ
MinFilter(k)      パラメタkを使ってぼかす?
ModeFilter(k)     kが大きくなるほど色の階調が荒く同系色にまとめられる

http://winnie.kuis.kyoto-u.ac.jp/~mizumoto/python/python_image.html
(前半)
>>> import Image, ImageFilter
>>> im = Image.open('c:/prj/ginkaku.jpg')
>>> im2 = im.filter(ImageFilter.CONTOUR)
>>> im2.save('c:/prj/ginkaku2.jpg')
>>> del im2
>>> del im
(後半:結果がおかしい)
画像の膨張 (dilate)
>>> import Image
>>> import numpy
>>> import scipy.ndimage
膨張させる元パターンを造る
>>> struct = numpy.array([
  [0, 0, 1, 0, 0],
  [0, 1, 1, 1, 0],
  [1, 1, 1, 1, 1],
  [0, 1, 1, 1, 0],
  [0, 0, 1, 0, 0]])
画像を読み込んでgray scale化
>>> im = Image.open('c:/prj/ginkaku2.jpg').convert('L')
numpy.array化して膨張させる。
>>> before = numpy.asarray(im)
>>> after = scipy.ndimage.binary_dilation(before, struct, 10)
>>> after = numpy.array(after, numpy.uint8) * 255
最後に画像を保存
>>> im2 = Image.fromarray(after, 'L')
>>> im2.save('c:/prj/ginkaku3.jpg')
>>> del im2
>>> del im

(Python2.5 PIL-1.1.6 numpy-1.3.0 scipy-0.7.1)
Usage:
  1. new product
    wxTurtle.py
  2. load file
    wxTurtle.py filename.turtle
'''

import sys, os
import time
import math
import wx
import threading
import turtle
import Tkinter as tk
import main_icon

APP_TITLE = u'wxTurtle'
APP_FILE = u'ファイル名'
APP_EXT = u'turtle'
APP_USAGE = u'''Usage:
  Left Click: mark
  Right Click: release
  SHIFT + Right Click: back and hold
  Right Double Click: back and release
  SHIFT + Left Click: redo or re-hold
'''
DEFAULT_PENWIDTH = 15
DEFAULT_COLOR = (240/256.0, 192/256.0, 32/256.0)
DEFAULT_SLEEP = 5
DEFAULT_WIDTH, DEFAULT_HEIGHT = 480, 480
DEFAULT_LISTWH = (160, 80)
DEFAULT_SIZE = (800, 600)
DEFAULT_POS = (20, 20)

def loaddata(fname):
  orbit = []
  if not os.path.exists(fname):
    wx.MessageBox(u'file is not found: %s' % fname, APP_TITLE, wx.OK)
  else:
    try:
      ifp = open(fname, 'rb')
      c = 0
      for line in ifp.readlines():
        c += 1
        p = map(float, line.rstrip().lstrip().split())
        orbit.append((int(p[0]), p[1], p[2]))
    except (IOError,), e:
      wx.MessageBox(u'file read error: %s' % fname, APP_TITLE, wx.OK)
    except (IndexError, ValueError), e:
      wx.MessageBox(u'bad data in [%s] line %d' % (fname, c), APP_TITLE, wx.OK)
    finally:
      if ifp: ifp.close()
  return orbit

def stepdraw(t, d):
  (t.down if d[0] else t.up)(); t.right(d[1]); t.forward(d[2]) # right: Ymirror

def getanglelength(ox, oy, nx, ny):
  dx, dy = nx - ox, ny - oy
  offset = (180.0 if dy >= 0.0 else -180.0) if dx < 0.0 else 0.0
  if dx == 0.0: a = 90.0 if dy > 0.0 else (-90.0 if dy < 0.0 else 0.0)
  else: a = offset + math.atan(float(dy) / float(dx)) * 180.0 / math.pi
  return (a, (dx * dx + dy * dy) ** .5)

def getnextpoint(p, qa, qx, qy):
  pa = qa + p[1]
  ra = pa * math.pi / 180.0
  return (pa, int(qx + p[2] * math.cos(ra)), int(qy + p[2] * math.sin(ra)))

class PALListCtrl(wx.ListCtrl):
  def __init__(self, parent=None, id=-1, size=DEFAULT_LISTWH,
    style=wx.LC_REPORT | wx.LC_HRULES):
    wx.ListCtrl.__init__(self, parent, id, size=size, style=style)
    for c, v in enumerate(['-', 'pen', 'angle', 'length']):
      self.InsertColumn(c, v)

  def appenddata(self, p):
    l = self.GetItemCount()
    for i, c in enumerate(p):
      if not i: self.InsertStringItem(l, str(l))
      self.SetStringItem(l, i + 1, str(c))

class TurtlePanel(wx.Panel):
  def __init__(self, parent=None, orbit=[]):
    wx.Panel.__init__(self, parent, size=(DEFAULT_WIDTH, DEFAULT_HEIGHT))
    self.parent = parent
    # self.shiftkey = False
    self.initState(orbit)
    self.SetBackgroundColour('Black')
    self.Bind(wx.EVT_PAINT, self.OnPaint)
    self.Bind(wx.EVT_MOTION, self.OnMotion)
    self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
    self.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
    self.Bind(wx.EVT_RIGHT_DCLICK, self.OnRightDclick)
    # self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    # self.Bind(wx.EVT_KEY_UP, self.OnKeyUp)

  def initState(self, orbit):
    self.redo = []
    self.orbit = orbit # (angle/10, length/10), ... (-angle = pen up)
    self.pendown = (orbit[-1][0] == 1) if len(orbit) else False
    self.angle = 0 # ->
    self.ox, self.oy = DEFAULT_WIDTH / 2, DEFAULT_HEIGHT / 2
    self.nx, self.ny = self.ox, self.oy

  def OnPaint(self, ev):
    # print u'paint'
    dc = wx.PaintDC(self)
    bdc = wx.BufferedDC(dc) # wx.BufferedPaintDC ?
    bdc.SetBrush(wx.BLACK_BRUSH)
    bdc.DrawRectangle(0, 0, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    bdc.SetPen(wx.CYAN_PEN)
    bdc.DrawLine(0, DEFAULT_HEIGHT / 2, DEFAULT_WIDTH, DEFAULT_HEIGHT / 2)
    bdc.DrawLine(DEFAULT_WIDTH / 2, 0, DEFAULT_WIDTH / 2, DEFAULT_HEIGHT)
    bdc.SetPen(wx.GREEN_PEN)
    if self.parent.chkrlst.GetValue():
      self.parent.rlst.DeleteAllItems()
      for p in self.redo: self.parent.rlst.appenddata(p)
    if self.parent.chkplst.GetValue(): self.parent.plst.DeleteAllItems()
    qa, qx, qy = 0, DEFAULT_WIDTH / 2, DEFAULT_HEIGHT / 2
    for p in self.orbit:
      if self.parent.chkplst.GetValue(): self.parent.plst.appenddata(p)
      pa, px, py = getnextpoint(p, qa, qx, qy)
      if p[0]: bdc.DrawLine(qx, qy, px, py)
      qa, qx, qy = pa, px, py
    self.angle, self.ox, self.oy = qa, qx, qy
    if self.pendown:
      bdc.DrawLine(self.ox, self.oy, self.nx, self.ny)
      bdc.SetBrush(wx.RED_BRUSH); bdc.SetPen(wx.RED_PEN)
    else:
      bdc.SetBrush(wx.CYAN_BRUSH); bdc.SetPen(wx.CYAN_PEN)
    bdc.DrawCircle(self.ox, self.oy, 4)
    self.parent.txtnx.SetLabel(u'X: %10d' % (self.nx - DEFAULT_WIDTH / 2))
    self.parent.txtny.SetLabel(u'Y: %10d' % -(self.ny - DEFAULT_HEIGHT / 2))
    self.parent.txtpc.SetLabel(u'Path count: %10d' % (len(self.orbit)))
    self.parent.txtrd.SetLabel(u'Redo count: %10d' % (len(self.redo)))

  def OnMotion(self, ev):
    # print u'motion %d, %d' % (ev.X, ev.Y)
    self.SetFocus() # need to get focus (after ListBox selection etc)
    self.nx, self.ny = ev.X, ev.Y
    self.Refresh(False)

  def OnLeftUp(self, ev):
    # print u'left up %d, %d' % (ev.X, ev.Y)
    # if self.shiftkey:
    if ev.ShiftDown():
      if not len(self.redo):
        self.pendown = True;
        self.Refresh()
        return
      p = self.redo.pop()
      # print u'redo'
      self.orbit.append(p)
      self.Refresh()
      return
    self.redo = []
    p = 1 if self.pendown else 0
    a, l = getanglelength(self.ox, self.oy, self.nx, self.ny)
    # print u'pen %d angle %f length %f' % (p, a, l)
    self.orbit.append((p, a - self.angle, l))
    self.angle = a
    self.pendown = True
    self.Refresh()

  def OnRightUp(self, ev):
    # print u'right up %d, %d' % (ev.X, ev.Y)
    # if self.shiftkey: self.OnRightDclick(ev); return
    if ev.ShiftDown(): self.OnRightDclick(ev); return
    # if ev.RightDClick(): return
    self.pendown = False
    self.Refresh()

  def OnRightDclick(self, ev):
    # print u'right dclick %d, %d' % (ev.X, ev.Y)
    if not len(self.orbit): return
    p = self.orbit.pop() # last item
    self.redo.append(p)
    self.pendown = True # (p[0] == 1)
    self.Refresh()

  # def OnKeyDown(self, ev):
  #   if ev.GetKeyCode() == wx.WXK_SHIFT: self.shiftkey = True

  # def OnKeyUp(self, ev):
  #   if ev.GetKeyCode() == wx.WXK_SHIFT: self.shiftkey = False

class MyFrame(wx.Frame):
  def __init__(self, parent=None, fname=None, orbit=[]):
    wx.Frame.__init__(self, parent, title=APP_TITLE,
      pos=DEFAULT_POS, size=DEFAULT_SIZE)
    self.th, self.t = None, None
    self.SetIcon(main_icon.getIcon())
    self.SetBackgroundColour('White')
    szh = wx.BoxSizer(wx.HORIZONTAL)
    self.tp = TurtlePanel(self, orbit)
    szh.Add(self.tp, 0, wx.FIXED)
    p = wx.Panel(self)
    # p.SetBackgroundColour('Green')
    szv = wx.BoxSizer(wx.VERTICAL)
    lbl = wx.StaticText(p, wx.NewId(), APP_USAGE)
    szv.Add(lbl, 1, wx.EXPAND | wx.ALIGN_TOP | wx.ALIGN_LEFT)
    self.chkplst = wx.CheckBox(p, wx.NewId(), u'Path (Pen, Angle and Length)')
    szv.Add(self.chkplst, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_LEFT)
    self.plst = PALListCtrl(p, wx.NewId())
    szv.Add(self.plst, 0, wx.EXPAND | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    self.txtpc = wx.StaticText(p, wx.NewId(), u'Path count:')
    szv.Add(self.txtpc, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_LEFT)
    self.chkrlst = wx.CheckBox(p, wx.NewId(), u'Undo / Redo buffer')
    szv.Add(self.chkrlst, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_LEFT)
    self.rlst = PALListCtrl(p, wx.NewId())
    szv.Add(self.rlst, 0, wx.EXPAND | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    self.txtrd = wx.StaticText(p, wx.NewId(), u'Redo count:')
    szv.Add(self.txtrd, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_LEFT)
    self.txtnx = wx.StaticText(p, wx.NewId(), u'X:')
    szv.Add(self.txtnx, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_LEFT)
    self.txtny = wx.StaticText(p, wx.NewId(), u'Y:')
    szv.Add(self.txtny, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_LEFT)
    self.flst = wx.ListBox(p, wx.NewId(), size=DEFAULT_LISTWH)
    szv.Add(self.flst, 0, wx.EXPAND | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    btnload = wx.Button(p, wx.NewId(), u'load')
    szv.Add(btnload, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    btnclear = wx.Button(p, wx.NewId(), u'clear')
    szv.Add(btnclear, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    btntest = wx.Button(p, wx.NewId(), u'testdraw')
    szv.Add(btntest, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    self.txtname = wx.TextCtrl(p, wx.NewId(),
      os.path.splitext(os.path.basename(fname))[0] if fname else APP_FILE)
    # size=DEFAULT_LISTWH, style=wx.TE_MULTILINE)
    szv.Add(self.txtname, 0, wx.EXPAND)
    btnsave = wx.Button(p, wx.NewId(), u'save')
    szv.Add(btnsave, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    btnquit = wx.Button(p, wx.NewId(), u'quit')
    szv.Add(btnquit, 0, wx.SHAPED | wx.ALIGN_BOTTOM | wx.ALIGN_RIGHT)
    p.SetSizer(szv)
    szh.Add(p, 1, wx.EXPAND)
    self.SetSizer(szh)
    self.initFileList()
    self.Bind(wx.EVT_CHECKBOX, self.OnCBplstClicked, self.chkplst)
    self.Bind(wx.EVT_CHECKBOX, self.OnCBrlstClicked, self.chkrlst)
    self.Bind(wx.EVT_LISTBOX, self.OnLBflstSelected, self.flst)
    self.Bind(wx.EVT_LISTBOX_DCLICK, self.OnLBflstDClicked, self.flst)
    self.Bind(wx.EVT_BUTTON, self.OnBtnLoad, btnload)
    self.Bind(wx.EVT_BUTTON, self.OnBtnClear, btnclear)
    self.Bind(wx.EVT_BUTTON, self.OnBtnTest, btntest)
    self.Bind(wx.EVT_BUTTON, self.OnBtnSave, btnsave)
    self.Bind(wx.EVT_BUTTON, self.OnBtnQuit, btnquit)
    self.Bind(wx.EVT_CLOSE, self.OnClose) # trap [x]
    if len(orbit): self.OnBtnTest(None)

  def initFileList(self):
    import glob
    self.flst.Clear()
    for fn in glob.glob(os.path.join(os.path.dirname(__file__),
      '*.%s' % APP_EXT)):
      if not os.path.isfile(fn): continue
      self.flst.Append(os.path.splitext(os.path.basename(fn))[0])
    self.Refresh()

  def checkDisposedOK(self, appname, cmd):
    if not len(self.tp.orbit): return True
    if wx.MessageBox(u'%s\ncurrent data will be disposed\nOK ?' % cmd,
      appname, wx.OK | wx.CANCEL) == wx.CANCEL:
      return False
    return True

  def OnCBplstClicked(self, ev):
    self.plst.DeleteAllItems()
    self.tp.Refresh(False)

  def OnCBrlstClicked(self, ev):
    self.rlst.DeleteAllItems()
    self.tp.Refresh(False)

  def OnLBflstSelected(self, ev):
    lb = ev.GetEventObject()
    sel = lb.GetSelection()
    if sel < 0: return
    s = lb.GetString(sel)
    # print u'filelist selected %s' % s
    self.txtname.SetValue(s)

  def OnLBflstDClicked(self, ev):
    lb = ev.GetEventObject()
    sel = lb.GetSelection()
    if sel < 0: return
    s = lb.GetString(sel)
    # print u'filelist double clicked %s' % s
    self.OnBtnLoad(None)

  def OnBtnLoad(self, ev):
    appname = self.GetTitle()
    sel = self.flst.GetSelection()
    if sel < 0:
      wx.MessageBox(u'please select a file name', appname, wx.OK)
      return
    name = os.path.join(os.path.dirname(__file__),
      u'%s.%s' % (self.flst.GetString(sel), APP_EXT))
    # print u'load %s' % name
    if not self.checkDisposedOK(appname, u'Load [%s]' % name): return
    self.tp.initState(loaddata(name))
    self.tp.Refresh()
    self.Refresh()
    if len(self.tp.orbit): self.OnBtnTest(None)

  def OnBtnClear(self, ev):
    appname = self.GetTitle()
    # print u'clear %s' % appname
    if not self.checkDisposedOK(appname, u'Clear'): return
    self.tp.initState([])
    self.tp.Refresh()
    self.Refresh()

  def OnBtnTest(self, ev):
    appname = self.GetTitle()
    # print u'testdraw %s' % appname
    def draw(self):
      reload(turtle) # need else next window is disappeared
      self.t = turtle.Turtle()
      # self.t.title(appname) # not implemented manual is not correct!!
      self.t.speed('fastest') # self.t.tracer(False)
      self.t.width(DEFAULT_PENWIDTH); self.t.color(*DEFAULT_COLOR)
      for d in self.tp.orbit: stepdraw(self.t, d)
      # self.t.done() # not implemented manual is not correct!!
      # after here codes exist for thread control
      # self.th.join()
      self.t.tracer(True); self.t.speed('slowest')
      self.t.width(0); self.t.color(1.0, 0.0, 0.0)
      try:
        while self.t:
          if self.t: self.t.forward(10)
          if self.t: self.t.backward(10)
      except (tk.TclError, wx.PyDeadObjectError), e:
        # raised tk.TclError when critical zone (self.t == None)
        # raised wx.PyDeadObjectError when close main window
        pass
      self.t = None # need at closed turtle window by [x]
      self.th = None
      # print u'done'
    if self.th:
      if wx.MessageBox(u'Test draw\nturtle is running\nforce stop it?',
        appname, wx.YES | wx.NO) == wx.NO: return
      if self.t:
        # del self.t # tk window is appeared
        self.t = None
        time.sleep(1) # wait for thread exit while
    self.th = threading.Thread(target=draw, args=(self, ))
    self.th.start()

  def OnBtnSave(self, ev):
    appname = self.GetTitle()
    name = os.path.join(os.path.dirname(__file__),
      u'%s.%s' % (self.txtname.GetValue(), APP_EXT))
    # print u'save %s' % name
    if os.path.exists(name):
      if wx.MessageBox(u'file [%s] already exists\noverwrite OK?' % name,
        appname, wx.YES | wx.NO) == wx.NO: return
    ofp = open(name, 'wb')
    for p in self.tp.orbit: ofp.write('%d %f %f\n' % p)
    ofp.close()
    self.initFileList()
    wx.MessageBox(u'saved %s' % name, appname, wx.OK)

  def OnBtnQuit(self, ev):
    # print u'quit'
    self.Close(True)

  def OnClose(self, ev):
    appname = self.GetTitle()
    # print u'close %s' % appname
    if not self.checkDisposedOK(appname, u'Quit'): return
    # if not self.CanVeto():
    self.Destroy()

if __name__ == '__main__':
  app = wx.App(False)
  fname = None
  orbit = []
  if len(sys.argv) >= 2:
    import locale
    orbit = loaddata(sys.argv[1].decode(locale.getpreferredencoding()))
  frm = MyFrame(None, fname, orbit)
  app.SetTopWindow(frm)
  frm.Show()
  app.MainLoop()
