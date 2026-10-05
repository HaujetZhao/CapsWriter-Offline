using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Diagnostics;
using System.Globalization;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;

namespace CapsWriterIndicator {
    enum Phase { Idle, Recording, Processing, Error }

    // Only log metadata drives this model; transcript contents are never retained.
    sealed class RecordingState {
        public Phase Phase = Phase.Idle;
        public DateTime Started = DateTime.UtcNow;
        public DateTime Changed = DateTime.UtcNow;
        public int Generation;
        public string ShortcutLabel = "";
        string currentTask = "";
        static readonly Regex StartTime = new Regex(@"start_time=([0-9.]+)");
        static readonly Regex TaskId = new Regex(@"(?:任务ID[:：]\s*|task_id=)([a-zA-Z0-9-]+)");
        static readonly Regex ShortcutTrigger = new Regex(@"\[([^\]]+)\]\s*触发：开始录音");
        public string ShortcutHint { get { return (ShortcutLabel.Length == 0 ? "快捷键" : ShortcutLabel) + " 停止"; } }
        public string SecondaryText {
            get { return Phase == Phase.Recording ? ShortcutHint : Phase == Phase.Error ? "请检查客户端" : ""; }
        }
        static string FormatKey(string key) {
            string k = key.Trim().ToLowerInvariant().Replace(' ', '_');
            switch (k) {
                case "alt_gr": case "alt_r": case "right_alt": case "ralt": return "右 Alt";
                case "alt_l": case "left_alt": case "lalt": return "左 Alt";
                case "ctrl": case "ctrl_l": case "ctrl_r": case "left_ctrl": case "right_ctrl": case "control": return "Ctrl";
                case "shift": case "shift_l": case "shift_r": case "left_shift": case "right_shift": return "Shift";
                case "cmd": case "cmd_l": case "cmd_r": case "win": case "windows": return "Win";
                case "caps_lock": case "capslock": return "Caps Lock";
                case "num_lock": case "numlock": return "Num Lock";
                case "scroll_lock": case "scrolllock": return "Scroll Lock";
                case "space": return "Space";
                case "enter": case "return": return "Enter";
                case "esc": case "escape": return "Esc";
                case "backspace": return "Backspace";
                case "delete": return "Delete";
                case "x1": return "鼠标侧键 1";
                case "x2": return "鼠标侧键 2";
            }
            if (k.StartsWith("numpad") && k.Length == 7 && Char.IsDigit(k[6])) return "小键盘 " + k[6];
            if (k.Length > 1 && k[0] == 'f') {
                int n; if (Int32.TryParse(k.Substring(1), out n) && n >= 1 && n <= 24) return "F" + n;
            }
            if (k.Length == 1) return k.ToUpperInvariant();
            string[] words = k.Replace('_', ' ').Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            for (int i = 0; i < words.Length; i++) words[i] = CultureInfo.InvariantCulture.TextInfo.ToTitleCase(words[i]);
            return String.Join(" ", words);
        }
        static string FormatShortcut(string key) {
            string[] parts = key.Split(new char[] { '+' }, StringSplitOptions.RemoveEmptyEntries);
            List<string> labels = new List<string>();
            foreach (string part in parts) labels.Add(FormatKey(part));
            return String.Join("+", labels.ToArray());
        }
        public void Set(Phase phase) { Phase = phase; Changed = DateTime.UtcNow; }
        public void Consume(string line) {
            Match shortcut = ShortcutTrigger.Match(line);
            if (shortcut.Success) ShortcutLabel = FormatShortcut(shortcut.Groups[1].Value);
            if (line.Contains("state.py:") && line.Contains("recording=True")) {
                Set(Phase.Recording); Started = DateTime.UtcNow; Generation++; currentTask="";
                Match m = StartTime.Match(line); double epoch;
                if (m.Success && Double.TryParse(m.Groups[1].Value, NumberStyles.Float,
                        CultureInfo.InvariantCulture, out epoch)) {
                    try { Started = new DateTime(1970,1,1,0,0,0,DateTimeKind.Utc).AddSeconds(epoch); }
                    catch (ArgumentOutOfRangeException) { }
                }
            } else if (line.Contains("recorder.py:") && line.Contains("创建录音任务")) {
                Match task = TaskId.Match(line); if(task.Success) currentTask=task.Groups[1].Value;
            } else if (line.Contains("state.py:") && line.Contains("recording=False")) {
                if (Phase == Phase.Recording) Set(Phase.Processing);
            } else if (line.Contains("task.py:") && line.Contains("取消录音任务")) {
                Set(Phase.Idle);
            } else if (line.Contains("text_output.py:") && line.Contains("已发送粘贴命令")) {
                // Actual client saves recordings. Its subsequent save event supplies
                // a task ID, so an older output cannot hide a newer pending task.
                if (Phase != Phase.Recording && currentTask.Length==0) Set(Phase.Idle);
            } else if (line.Contains("state.py:") && line.Contains("获取音频文件:")) {
                Match task=TaskId.Match(line);
                if (Phase != Phase.Recording && (currentTask.Length==0 ||
                    (task.Success && task.Groups[1].Value==currentTask))) Set(Phase.Idle);
            } else if ((line.Contains("录音任务错误") || line.Contains("连接异常中断") ||
                        line.Contains("WebSocket 连接已关闭")) && Phase != Phase.Idle) {
                Set(Phase.Error);
            }
        }
        public string Elapsed {
            get {
                int seconds = (int)Math.Max(0, (DateTime.UtcNow - Started).TotalSeconds);
                return (seconds / 60).ToString("00") + ":" + (seconds % 60).ToString("00");
            }
        }
    }

    sealed class LogTail {
        readonly string path;
        long offset;
        DateTime creation;
        bool initialized;
        Decoder decoder = Encoding.UTF8.GetDecoder();
        readonly StringBuilder pending = new StringBuilder();
        readonly byte[] buffer = new byte[8192];
        readonly char[] chars = new char[8192];
        public LogTail(string file) { path = file; }
        public void Poll(RecordingState state) {
            try {
                FileInfo info = new FileInfo(path);
                if (!info.Exists) return;
                bool reset = !initialized || info.Length < offset || info.CreationTimeUtc != creation;
                using (FileStream f = new FileStream(path, FileMode.Open, FileAccess.Read,
                        FileShare.ReadWrite | FileShare.Delete)) {
                    if (reset) {
                        state.Set(Phase.Idle); decoder.Reset(); pending.Clear();
                        offset = Math.Max(0, f.Length - 131072);
                        creation = info.CreationTimeUtc; initialized = true;
                        if (offset > 0) {
                            f.Position = offset;
                            while (f.Position < f.Length && f.ReadByte() != 10) { }
                            offset = f.Position;
                        }
                    }
                    f.Position = offset; int count;
                    // Bound each UI poll; do not scan an ever-growing transcript history.
                    long end = Math.Min(f.Length, offset + 1048576);
                    while (f.Position < end && (count = f.Read(buffer,0,(int)Math.Min(buffer.Length,end-f.Position))) > 0) {
                        int n = decoder.GetChars(buffer,0,count,chars,0,false);
                        for (int i=0;i<n;i++) {
                            if (chars[i] == '\n') {
                                state.Consume(pending.ToString()); pending.Clear();
                            } else {
                                pending.Append(chars[i]);
                                if (pending.Length > 65536) pending.Clear();
                            }
                        }
                    }
                    offset = f.Position;
                }
            } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }

    static class Native {
        public const int NoActivate = 0x08000000, ToolWindow = 0x80, Transparent = 0x20;
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after,
            int x, int y, int w, int height, uint flags);
        [DllImport("user32.dll", EntryPoint="GetWindowLong")] public static extern int GetWindowLong(IntPtr h,int index);
        [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
        [StructLayout(LayoutKind.Sequential)] struct Point { public int X,Y; }
        [StructLayout(LayoutKind.Sequential)] struct Size { public int Width,Height; }
        [StructLayout(LayoutKind.Sequential,Pack=1)] struct Blend { public byte Op,Flags,Alpha,Format; }
        [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr h);
        [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr h,IntPtr dc);
        [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleDC(IntPtr dc);
        [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr dc);
        [DllImport("gdi32.dll")] static extern IntPtr SelectObject(IntPtr dc,IntPtr obj);
        [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);
        [DllImport("user32.dll",SetLastError=true)] static extern bool UpdateLayeredWindow(IntPtr h,IntPtr dst,ref Point pos,ref Size size,IntPtr src,ref Point origin,int key,ref Blend blend,int flags);
        public static void Present(IntPtr h,Bitmap bitmap,Rectangle bounds) {
            IntPtr screen=GetDC(IntPtr.Zero), memory=IntPtr.Zero, image=IntPtr.Zero,old=IntPtr.Zero;
            try {
                memory=CreateCompatibleDC(screen); image=bitmap.GetHbitmap(Color.FromArgb(0)); old=SelectObject(memory,image);
                Point pos=new Point {X=bounds.X,Y=bounds.Y}, origin=new Point();
                Size size=new Size {Width=bitmap.Width,Height=bitmap.Height};
                Blend blend=new Blend {Alpha=255,Format=1};
                if(!UpdateLayeredWindow(h,screen,ref pos,ref size,memory,ref origin,0,ref blend,2))
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            } finally {
                if(old!=IntPtr.Zero)SelectObject(memory,old);
                if(image!=IntPtr.Zero)DeleteObject(image);
                if(memory!=IntPtr.Zero)DeleteDC(memory);
                if(screen!=IntPtr.Zero)ReleaseDC(IntPtr.Zero,screen);
            }
        }
    }

    sealed class Overlay : Form {
        readonly RecordingState state;
        float dpiScale=1;
        float scale=.75f;
        int logicalWidth=360;
        int logicalHeight=90;
        int positionedGeneration=-1;
        Phase lastPhase=Phase.Idle;
        public Overlay(RecordingState model) {
            state=model;
            Text="CapsWriter 录音状态"; FormBorderStyle=FormBorderStyle.None;
            ShowInTaskbar=false; TopMost=true; AutoScaleMode=AutoScaleMode.None;
            BackColor=Color.FromArgb(25,28,35); ForeColor=Color.White;
            DoubleBuffered=true; SetStyle(ControlStyles.Selectable,false);
            ClientSize=new Size(360,90);
        }
        protected override bool ShowWithoutActivation { get { return true; } }
        protected override CreateParams CreateParams {
            get { CreateParams cp=base.CreateParams;
                cp.ExStyle |= Native.NoActivate | Native.ToolWindow | Native.Transparent | 0x80000; // layered alpha edges
                return cp;
            }
        }
        protected override void WndProc(ref Message m) {
            if (m.Msg==0x21) { m.Result=new IntPtr(3); return; } // MA_NOACTIVATE
            if (m.Msg==0x84) { m.Result=new IntPtr(-1); return; } // HTTRANSPARENT
            base.WndProc(ref m);
        }
        static GraphicsPath Rounded(RectangleF r,float radius) {
            GraphicsPath p=new GraphicsPath(); float d=radius*2;
            p.AddArc(r.X,r.Y,d,d,180,90); p.AddArc(r.Right-d,r.Y,d,d,270,90);
            p.AddArc(r.Right-d,r.Bottom-d,d,d,0,90); p.AddArc(r.X,r.Bottom-d,d,d,90,90);
            p.CloseFigure(); return p;
        }
        void PositionPill() {
            IntPtr active=Native.GetForegroundWindow();
            Screen screen=active==IntPtr.Zero ? Screen.FromPoint(Cursor.Position) : Screen.FromHandle(active);
            try { dpiScale=Math.Max(1,Native.GetDpiForWindow(active)/96f); } catch(EntryPointNotFoundException) {dpiScale=1;}
            scale=dpiScale*.75f;
            logicalWidth=PreferredWidth();
            logicalHeight=state.Phase==Phase.Recording?90:78;
            int w=(int)Math.Round(logicalWidth*scale), h=(int)Math.Round(logicalHeight*scale);
            if(ClientSize.Width!=w || ClientSize.Height!=h) ClientSize=new Size(w,h);
            Rectangle work=screen.WorkingArea;
            int x=work.Left+(work.Width-w)/2, y=work.Bottom-h-(int)Math.Round(24*scale);
            Native.SetWindowPos(Handle,new IntPtr(-1),x,y,w,h,0x10|0x40); // NOACTIVATE | SHOWWINDOW
        }
        int PreferredWidth() {
            if(state.Phase!=Phase.Recording)return 360;
            using(Font font=new Font("Microsoft YaHei UI",18.67f,FontStyle.Regular,GraphicsUnit.Pixel)) {
                int text=TextRenderer.MeasureText(state.ShortcutHint,font,new Size(4096,40),TextFormatFlags.NoPadding|TextFormatFlags.SingleLine).Width;
                text=(int)Math.Ceiling(text/dpiScale);
                return Math.Max(360,Math.Min(620,278+text));
            }
        }
        public void Sync() {
            if(state.Phase==Phase.Idle) { if(Visible) Hide(); lastPhase=Phase.Idle; return; }
            if(!Visible || positionedGeneration!=state.Generation || lastPhase!=state.Phase) {
                PositionPill(); if(!Visible) Show();
                // Reassert native bounds after crossing a monitor DPI boundary.
                PositionPill(); positionedGeneration=state.Generation;
            }
            if(lastPhase!=state.Phase) lastPhase=state.Phase;
            using(Bitmap surface=SnapshotSurface()) {
                Native.Present(Handle,surface,Bounds);
            }
        }
        public Bitmap SnapshotSurface() {
            Bitmap surface=new Bitmap(Width,Height,System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
            using(Graphics canvas=Graphics.FromImage(surface))
                OnPaint(new PaintEventArgs(canvas,new Rectangle(Point.Empty,surface.Size)));
            return surface;
        }
        protected override void OnPaint(PaintEventArgs e) {
            Graphics g=e.Graphics; g.SmoothingMode=SmoothingMode.AntiAlias;
            g.Clear(Color.Transparent);
            g.PixelOffsetMode=PixelOffsetMode.HighQuality;
            g.ScaleTransform(scale,scale);
            using(GraphicsPath fill=Rounded(new RectangleF(.5f,.5f,logicalWidth-1,logicalHeight-1),logicalHeight/2f-.5f))
            using(SolidBrush background=new SolidBrush(BackColor))g.FillPath(background,fill);
            // Keep the outline one physical pixel even as the pill scales.
            float inset=.5f/scale;
            using(GraphicsPath border=Rounded(new RectangleF(inset,inset,logicalWidth-2*inset,logicalHeight-2*inset),logicalHeight/2f-inset))
            using(Pen pen=new Pen(Color.FromArgb(110,155,160,170),1f/scale))g.DrawPath(pen,border);
            bool recording=state.Phase==Phase.Recording;
            if(recording) {
                using(SolidBrush red=new SolidBrush(Color.FromArgb(255,78,86)))g.FillEllipse(red,29,32,25,25);
                using(Font title=new Font("Microsoft YaHei UI",21.33f,FontStyle.Bold,GraphicsUnit.Pixel))
                using(SolidBrush white=new SolidBrush(Color.FromArgb(245,247,250)))g.DrawString("正在录音",title,white,80,14);
                using(Font timer=new Font("Segoe UI",20,FontStyle.Regular,GraphicsUnit.Pixel))
                using(SolidBrush light=new SolidBrush(Color.FromArgb(220,225,234)))g.DrawString(state.Elapsed,timer,light,81,47);
                using(Pen divider=new Pen(Color.FromArgb(85,160,173,189)))g.DrawLine(divider,211,18,211,72);
                using(Font hint=new Font("Microsoft YaHei UI",18.67f,FontStyle.Regular,GraphicsUnit.Pixel))
                using(SolidBrush gray=new SolidBrush(Color.FromArgb(190,198,211)))
                using(StringFormat fmt=new StringFormat {LineAlignment=StringAlignment.Center,FormatFlags=StringFormatFlags.NoWrap})
                    g.DrawString(state.ShortcutHint,hint,gray,new RectangleF(236,0,logicalWidth-250,logicalHeight),fmt);
            } else {
                using(Pen bars=new Pen(Color.FromArgb(218,227,239),4)) {
                    bars.StartCap=LineCap.Round;bars.EndCap=LineCap.Round;
                    g.DrawLine(bars,35,33,35,45);g.DrawLine(bars,47,28,47,50);g.DrawLine(bars,59,34,59,46);
                }
                using(Font title=new Font("Microsoft YaHei UI",21.33f,FontStyle.Regular,GraphicsUnit.Pixel))
                using(SolidBrush white=new SolidBrush(Color.FromArgb(237,242,249)))
                    g.DrawString(state.Phase==Phase.Processing?"正在识别…":"连接异常",title,white,83,21);
            }
            base.OnPaint(e);
        }
    }

    sealed class IndicatorContext : ApplicationContext {
        readonly RecordingState state=new RecordingState();
        readonly Overlay form;
        readonly LogTail tail;
        readonly System.Windows.Forms.Timer timer=new System.Windows.Forms.Timer();
        int ticks;
        readonly DateTime boot=DateTime.UtcNow;
        public IndicatorContext(string log) {
            tail=new LogTail(log); form=new Overlay(state);
            timer.Interval=100; timer.Tick+=Tick; timer.Start();
        }
        void Tick(object sender,EventArgs e) {
            tail.Poll(state);
            if(state.Phase==Phase.Error && (DateTime.UtcNow-state.Changed).TotalSeconds>5) state.Set(Phase.Idle);
            if(++ticks%20==0) {
                Process[] clients=Process.GetProcessesByName("start_client");
                bool running=clients.Length>0; foreach(Process p in clients) p.Dispose();
                if(!running) { state.Set(Phase.Idle); form.Sync();
                    if((DateTime.UtcNow-boot).TotalSeconds>15) { ExitThread(); return; }
                }
            }
            form.Sync();
        }
        protected override void ExitThreadCore() { timer.Stop(); timer.Dispose(); form.Dispose(); base.ExitThreadCore(); }
    }

    static class Program {
        static void Assert(bool ok,string text) { if(!ok) throw new Exception(text); }
        static string StateLine(bool recording) {
            return "13:00:00 DEBUG [state.py:117] 录音状态已更新: recording="+
                (recording ? "True, start_time="+(DateTime.UtcNow-new DateTime(1970,1,1)).TotalSeconds.ToString(CultureInfo.InvariantCulture)
                           : "False, duration=2.00s");
        }
        static void SelfTest(string dir) {
            Directory.CreateDirectory(dir);
            RecordingState s=new RecordingState();
            s.Consume("15:00:00 INFO [task.py:75] [alt_gr] 触发：开始录音");
            Assert(s.ShortcutLabel=="右 Alt" && s.ShortcutHint=="右 Alt 停止","right Alt shortcut formatting");
            s.Consume(StateLine(true)); Assert(s.Phase==Phase.Recording,"begin");
            Assert(s.SecondaryText=="右 Alt 停止","recording shortcut copy");
            s.Consume("[text_output.py:128] 已发送粘贴命令 (Ctrl+V)"); Assert(s.Phase==Phase.Recording,"old result hides new recording");
            s.Consume(StateLine(false)); Assert(s.Phase==Phase.Processing,"stop");
            Assert(s.SecondaryText=="","processing shows only recognition copy");
            s.Consume("[text_output.py:128] 已发送粘贴命令 (Ctrl+V)"); Assert(s.Phase==Phase.Idle,"paste");
            s.Consume("15:00:01 INFO [task.py:75] [ctrl+shift+f12] 触发：开始录音");
            Assert(s.ShortcutLabel=="Ctrl+Shift+F12","dynamic key combination formatting");
            s.Consume(StateLine(true)); s.Consume("[recorder.py:92] 创建录音任务，任务ID: new-task");
            s.Consume(StateLine(false));
            s.Consume("[text_output.py:128] 已发送粘贴命令 (Ctrl+V)");
            s.Consume("[state.py:168] 获取音频文件: task_id=old-task, path=test.wav");
            Assert(s.Phase==Phase.Processing,"older result hid newer processing");
            s.Consume("[state.py:168] 获取音频文件: task_id=new-task, path=test.wav");
            Assert(s.Phase==Phase.Idle,"task-correlated completion");
            s.Consume(StateLine(true)); s.Consume("[task.py:102] 取消录音任务（时间过短）");
            s.Consume(StateLine(false)); Assert(s.Phase==Phase.Idle,"cancel");
            string log=Path.Combine(dir,"fixture.log"); File.WriteAllText(log,"",new UTF8Encoding(false));
            LogTail tail=new LogTail(log); tail.Poll(s);
            string start=StateLine(true); File.AppendAllText(log,start.Substring(0,20),Encoding.UTF8); tail.Poll(s);
            Assert(s.Phase==Phase.Idle,"partial line");
            File.AppendAllText(log,start.Substring(20)+"\n",Encoding.UTF8); tail.Poll(s);
            Assert(s.Phase==Phase.Recording,"append");
            RecordingState recover=new RecordingState(); new LogTail(log).Poll(recover);
            Assert(recover.Phase==Phase.Recording,"startup recovery");
            File.WriteAllText(log,"[task.py:102] 取消录音任务\n",new UTF8Encoding(false)); tail.Poll(s);
            Assert(s.Phase==Phase.Idle,"truncation");
            s.Consume("15:00:02 INFO [task.py:75] [alt_gr] 触发：开始录音");
            s.Consume(StateLine(true));
            using(Overlay form=new Overlay(s)) {
                IntPtr before=Native.GetForegroundWindow(); form.Sync(); Application.DoEvents();
                Assert(Native.GetForegroundWindow()==before,"show stole focus");
                int flags=Native.GetWindowLong(form.Handle,-20);
                int required=Native.NoActivate|Native.ToolWindow|Native.Transparent;
                Assert((flags&required)==required,"window flags");
                Assert(!form.ShowInTaskbar,"taskbar entry");
                Thread.Sleep(350); Application.DoEvents();
                using(Bitmap b=new Bitmap(form.Bounds.Width,form.Bounds.Height))
                using(Graphics screen=Graphics.FromImage(b)) { screen.CopyFromScreen(form.Bounds.Location,Point.Empty,b.Size); b.Save(Path.Combine(dir,"live-recording.png")); }
                using(Bitmap b=form.SnapshotSurface()) {
                    Assert(b.GetPixel(0,0).A==0,"outer corner is opaque");
                    Assert(b.GetPixel(b.Width/2,b.Height/2).A==255,"pill interior is translucent");
                    int smooth=0; for(int x=0;x<b.Width;x++)for(int y=0;y<b.Height;y++){int a=b.GetPixel(x,y).A;if(a>0&&a<255)smooth++;}
                    Assert(smooth>0,"rounded edge has no antialias coverage");
                    b.Save(Path.Combine(dir,"recording.png"));
                }
                s.Consume(StateLine(false)); form.Sync(); Application.DoEvents();
                Thread.Sleep(350); Application.DoEvents();
                using(Bitmap b=new Bitmap(form.Bounds.Width,form.Bounds.Height))
                using(Graphics screen=Graphics.FromImage(b)) { screen.CopyFromScreen(form.Bounds.Location,Point.Empty,b.Size); b.Save(Path.Combine(dir,"live-processing.png")); }
                using(Bitmap b=form.SnapshotSurface()) { b.Save(Path.Combine(dir,"processing.png")); }
                s.Set(Phase.Idle); form.Sync(); Application.DoEvents();
                Assert(!form.Visible,"idle visible"); Assert(Native.GetForegroundWindow()==before,"hide stole focus");
                File.WriteAllText(Path.Combine(dir,"verification.txt"),"PASS: recording/processing/output/cancellation/overlap/partial-line/recovery/truncation.\r\nPASS: native show/hide preserves foreground, NOACTIVATE + TRANSPARENT + TOOLWINDOW.\r\nSolid dark background; no transparency or backdrop material.\r\nForeground HWND: "+before+"\r\nExtended style: 0x"+flags.ToString("X")+"\r\nBounds: "+form.Bounds+"\r\n",Encoding.UTF8);
            }
        }
        [STAThread] static int Main(string[] args) {
            try {
                try { Native.SetProcessDpiAwarenessContext(new IntPtr(-4)); } catch(EntryPointNotFoundException) { }
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
                if(args.Length==2 && args[0]=="--self-test") { SelfTest(args[1]); return 0; }
                bool first; using(Mutex mutex=new Mutex(true,"Local\\CapsWriterRecordingIndicator",out first)) {
                    if(!first) return 0;
                    string app=Environment.GetEnvironmentVariable("CAPSWRITER_APP_DIR");
                    if(String.IsNullOrWhiteSpace(app)) app=Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","app","CapsWriter-Offline"));
                    else app=Path.GetFullPath(app);
                    string log=Path.Combine(app,"logs","client_latest.log");
                    Application.Run(new IndicatorContext(log));
                }
                return 0;
            } catch(Exception e) {
                File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"overlay-error.txt"),e.ToString()); return 1;
            }
        }
    }
}
