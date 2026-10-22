"""Build the landscape assembly guide from native SolidCraft view exports.
Run with Python plus reportlab and ezdxf. No CAD geometry is generated here.
"""
from pathlib import Path
import json, math
import ezdxf
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
ROOT=Path(__file__).resolve().parents[2]
VERSION=json.loads((ROOT/'package.json').read_text())['version']
ASSETS=Path(__file__).parent/'assets'
OUT=ROOT/'docs/Halloween-LEDs-Build-Guide.pdf'
W,H=720,405
c=canvas.Canvas(str(OUT),pagesize=(W,H),pageCompression=1)
c.setTitle(f'Halloween LEDs v{VERSION} | Build guide')
c.setAuthor('Halloween LEDs project contributors')
c.setSubject(f'Illustrated assembly, wiring and commissioning; v{VERSION} experimental edition')
INK='#252B30';GRAY='#68737C';BLUE='#147CAD';LIGHT='#B9C0C5';RULE='#D4DADF'
page=0

def text(s,x,y,size=10,color=INK,bold=False):
 c.setFillColor(HexColor(color));c.setFont('Helvetica-Bold' if bold else 'Helvetica',size);c.drawString(x,H-y,s)
def para(s,x,y,w,size=10,color=INK):
 p=Paragraph(s,ParagraphStyle('p',fontName='Helvetica',fontSize=size,leading=size*1.38,textColor=HexColor(color)))
 _,h=p.wrap(w,H);assert y+h<375,(page,s[:45],y+h);p.drawOn(c,x,H-y-h);return y+h

def start(n,title,sub=''):
 global page;page+=1
 c.setFillColor(HexColor('#FFFFFF'));c.rect(0,0,W,H,fill=1,stroke=0)
 c.bookmarkPage(str(page));c.addOutlineEntry(f'{n} {title}',str(page),0)
 text(n,26,32,17,bold=True);text(title,87,32,16,bold=True)
 if sub: text(sub,87,50,8,GRAY)
def end():
 c.setStrokeColor(HexColor(RULE));c.setLineWidth(.4);c.line(26,29,694,29)
 text(f'Halloween LEDs  /  v{VERSION} experimental  /  CAD 294cd1f · 22 Oct 2026',26,391,7,GRAY)
 text(f'{page:02}',679,391,8,GRAY);c.showPage()
def tag(s,x,y=65,w=142):
 c.setDash(1,2);c.setStrokeColor(HexColor(LIGHT));c.setLineWidth(.6);c.roundRect(x,H-y-24,w,24,3,fill=0,stroke=1);c.setDash()
 text(s,x+9,y+15,8,bold=True)
def steps(items,x=28,y=112,w=205):
 for number,body in items:
  text(number,x,y+10,10,BLUE,True)
  y=para(body,x+29,y,w-29,10)+19
 return y

def lines(name):
 result=[]
 for p in sorted(ASSETS.glob(name+'-*.dxf')):
  seg=[]
  for e in ezdxf.readfile(p).modelspace():
   if e.dxftype()=='LINE':seg.append((e.dxf.start.x,e.dxf.start.y,e.dxf.end.x,e.dxf.end.y))
   else:raise ValueError(e.dxftype())
  result.append(seg)
 return result

def cad(name,x,y,w,h):
 layers=lines(name);assert layers and any(layers),name
 pts=[(a,b) for segs in layers for s in segs for a,b in [(s[0],s[1]),(s[2],s[3])]]
 lo=[min(p[i] for p in pts) for i in [0,1]];hi=[max(p[i] for p in pts) for i in [0,1]]
 k=min(w/(hi[0]-lo[0]),h/(hi[1]-lo[1]));ox=x+(w-k*(hi[0]-lo[0]))/2;oy=H-y-h+(h-k*(hi[1]-lo[1]))/2
 for i,segs in enumerate(layers):
  c.setStrokeColor(HexColor('#A0A9B1' if i==0 and len(layers)>1 else BLUE));c.setLineWidth(.38 if i==0 else .55)
  p=c.beginPath()
  for a,b,d,e in segs:p.moveTo(ox+(a-lo[0])*k,oy+(b-lo[1])*k);p.lineTo(ox+(d-lo[0])*k,oy+(e-lo[1])*k)
  c.drawPath(p)
 return (ox,oy,k)
def note(s,y=343):para(s,270,y,420,8,GRAY)
def assembly(n,title,tags,items,drawing,caption):
 start(n,title,'Gray: existing parts   /   Blue: parts added in this step   /   Exploded spacing is illustrative')
 for i,t in enumerate(tags):tag(t,270+i*143,w=137)
 steps(items);cad(drawing,265,104,425,226);note(caption);end()
def link(label,url,x,y,w=630):return para(f'<link href="{url}" color="{BLUE}">{label}</link>',x,y,w,9)

start('','Halloween LEDs',f'Build guide · v{VERSION} experimental')
text('A small light you can build,',28,104,24,bold=True);text('program and modify.',28,135,24,bold=True)
para('Two RGB LED sticks. Battery power. Local browser controls. Four printed parts with editable SolidCraft sketches and operations.',30,158,285,12)
cad('assembled',348,82,340,225)
para(f'<b>Final CAD handoff · 294cd1f</b><br/>Assembly illustrations and four printable STLs match the saved mechanical design from 22 October 2026. Digital mesh checks pass. Hardware qualification is in progress; v{VERSION} is experimental.',30,266,285,9)
para('Build-guide presentation inspired by <link href="https://www.curvlab.com/guides/wr1-build" color="'+BLUE+'">CURV LAB\'s WR1 Chassis Build Guide</link>. Assembly illustrations come from this project\'s own CAD.',361,320,324,8,GRAY);end()

start('0.1','Before you begin')
steps([('01','Read the electrical steps before soldering. Keep USB and the battery disconnected while wiring or fitting hardware.'),('02','Use a multimeter to verify polarity, shorts and boost output. The installed boost arrived at 12 V and required removal of two selection resistors.'),('03','Print the four supplied enclosure parts. Gather the listed electronics and hardware before starting assembly.')],w=318,y=86)
text('Tools',382,101,13,bold=True)
para('PETG printer and slicer<br/>Temperature-controlled soldering iron<br/>M2/M3 heat-set tips or suitable insertion tool<br/>Multimeter, flush cutters and wire stripper<br/>2.5 mm and 1.3 mm hex drivers<br/>Calipers, tweezers, heat-shrink tubing<br/>USB-C <b>data</b> cable and computer',382,115,298,11)
para('Physical fit, temperature rise, battery runtime and cutoff behavior remain to be qualified. Use indoors: the enclosure has no weatherproof rating. Keep a LiPo pouch free of sharp edges, pinching and screw tips.',382,276,298,9,GRAY);end()

start('0.2','Electronics shopping list','Quantities are per completed light; product names link to their sources.')
rows=[('1','ESP32-S2 Feather · Adafruit 5000','https://www.adafruit.com/product/5000','Use this exact board, not another Feather footprint.'),('2','8-pixel RGB NeoPixel stick · Adafruit 1426','https://www.adafruit.com/product/1426','RGB / GRB data; do not substitute the RGBW version.'),('1','3.7 V 2000 mAh LiPo · Adafruit 2011','https://www.adafruit.com/product/2011','Feather-compatible JST polarity; verify replacement packs.'),('1','TMF002 boost module · Teyleten Robot','https://www.amazon.com/dp/B0B4TB9QNY','Installed board: remove two selection resistors for 5 V; see step 4.3.')]
y=84
for qty,label,url,desc in rows:
 text(qty+'×',29,y+12,14,bold=True);link(label,url,75,y);para(desc,75,y+19,600,9,GRAY);y+=58
para('Also needed: flexible insulated hookup wire sized for the measured LED load, solder, heat-shrink, a thin nonconductive battery pad and a USB-C data cable. Wire lengths depend on routing; leave service slack without crossing screw posts.',29,326,650,9);end()

start('0.3','Fasteners and printed parts','Hardware quantities below include every modeled screw, insert and dowel.')
rows=[('6','M3 × 8 socket-head screw','4 close the case; 2 attach the LED frame. 2.5 mm hex.'),('6','M2 × 8 button-head screw','4 hold LED boards; 2 hold Feather frame. 1.3 mm hex.'),('6','Ruthex RX-M3×5.7 insert','4 in base; 2 in faceplate.'),('6','Ruthex RX-M2×4 insert','4 in LED retainer; 2 in base.'),('2','2 × 6 mm metal dowel','Locate the Feather on the opposite side from its screws.')]
y=85
for qty,label,desc in rows:
 text(qty+'×',28,y+11,12,bold=True);link(label, {'M3 × 8 socket-head screw':'https://www.amazon.com/s?k=stainless+M3+socket+head+screw+assortment','M2 × 8 button-head screw':'https://www.amazon.com/s?k=stainless+M2+button+head+screw+assortment'}.get(label,'https://www.ruthex.de' if 'Ruthex' in label else 'https://www.amazon.com/s?k=stainless+2mm+dowel+pin+assortment'),69,y,355);para(desc,69,y+19,355,8.5,GRAY);y+=46
para('<b>Ordinary assortment packs</b><br/>The original build used Amazon stainless screw and dowel mix packs. Choose the sizes listed here and check that screw heads fit the recesses.',458,86,226,10)
para('<b>Print one each</b><br/>Base<br/>Faceplate<br/>LED retainer<br/>Feather retainer',458,173,226,10)
link('Ruthex M3 inserts','https://www.ruthex.de/products/ruthex-gewindeeinsatz-m3-100-stuck-rx-m3x5-7-messing-gewindebuchsen',29,329,170)
link('Ruthex M2 inserts','https://www.ruthex.de/collections/gewindeeinsatze/products/ruthex-gewindeeinsatz-m2-70-stuck-rx-m2x4-messing-gewindebuchsen',230,329,170)
link('2 × 6 mm dowels','https://www.amazon.com/s?k=stainless+2mm+dowel+pin+assortment',440,329,230)
para('Screw and dowel links open Amazon searches for assortment packs. No particular brand is required.',29,349,650,8,GRAY);end()

start('1.0','Print and inspect the four parts','PETG · 0.4 mm nozzle · 0.20 mm layers · 4 perimeters · supports off')
for i,(name,label,orient) in enumerate([('base','Base','Flat underside down; cavity up.'),('faceplate','Faceplate','Exterior LED face down; posts up.'),('led-retainer','LED retainer','Broad frame down; PCB rails up.'),('feather-retainer','Feather retainer','Broad top face down; sleeves up.')]):
 x=28+i*174;cad('print-'+name,x,86,150,142);text(label,x,254,11,bold=True);para(orient,x,265,150,9)
para('Drawings identify parts; orient them as described in your slicer. Use your tested PETG material profile. All parts fit a 180 × 180 mm bed. Inspect USB bridging, insert holes and thin screw wells. Remove strings and burrs without altering bearing faces.',28,320,657,9)
end()

assembly('2.0','Heat-set the base inserts',['Base  ×1','M3 inserts  ×4','M2 inserts  ×2'],[('2.1','Install four M3 inserts in the corner closure posts.'),('2.2','Install two M2 inserts in the USB-side Feather support pads.'),('2.3','Seat every insert flush and square. Let the plastic cool completely before adding electronics.')],'base-inserts','The four tall corner posts take M3; the two lower USB-side pads take M2. Inserts are lifted for clarity.')
assembly('2.4','Heat-set the faceplate inserts',['Faceplate  ×1','M3 inserts  ×2'],[('2.4','Turn the faceplate over. Insert one M3 insert into each of the two underside retainer bosses.'),('2.5','Keep the iron square. Stop at flush; do not push through the blind roof.'),('2.6','Let both bosses cool before fitting the LED frame.')],'lid-inserts','Underside view. These two inserts attach the LED retainer; the four corner holes are case screw clearances.')
assembly('3.0','Prepare the LED retainer',['LED retainer  ×1','M2 inserts  ×4'],[('3.1','Heat-set four M2 inserts into the frame’s PCB mounting pockets.'),('3.2','Seat them flush with the PCB support surface. These pockets are open through the frame, with no bottom stop.'),('3.3','Inspect the support rails and clear any debris before placing a board.')],'retainer-inserts','The locating collars and PCB rails are integral parts of the printed LED retainer.')
assembly('3.4','Mount the two LED sticks',['RGB sticks  ×2','M2 × 8 screws  ×4'],[('3.4','Prepare the wires while both sides of the boards are accessible. Identify DIN, DOUT, 5V and GND from the actual silkscreen.'),('3.5','Place both boards with LEDs facing outward and mounting-hole edges facing inward. The two sticks face opposite directions.'),('3.6','Fit four M2 × 8 button-head screws. Tighten gently onto the mounting pads.')],'led-mount','Data direction follows DIN/DOUT, not the mechanical left/right orientation. Screw tips project about 0.4 mm below the retainer.')
assembly('3.7','Attach the LED assembly to the lid',['Lid assembly  ×1','LED assembly  ×1','M3 × 8 screws  ×2'],[('3.7','Place the LEDs into the faceplate recesses from underneath.'),('3.8','Align the retainer collars with the lid bosses. Keep solder joints and leads clear of the bearing surfaces.'),('3.9','Fit two M3 screws from the underside. Check that every LED lines up with its aperture.')],'lid-mount','Underside view. Install the four LED-board screws first: the faceplate covers their heads once assembled.')

# Vector wiring diagram: electrical net topology, not physical pin locations.
def box(label,x,y,w,h=43):
 c.setStrokeColor(HexColor(LIGHT));c.setFillColor(HexColor('#F7F9FA'));c.setLineWidth(.7);c.rect(x,H-y-h,w,h,fill=1,stroke=1);para(label,x+9,y+8,w-18,9)
def wire(points,col=BLUE,dash=False):
 c.setStrokeColor(HexColor(col));c.setLineWidth(1.3);c.setDash(4,2) if dash else c.setDash()
 p=c.beginPath();p.moveTo(points[0][0],H-points[0][1])
 for x,y in points[1:]:p.lineTo(x,H-y)
 c.drawPath(p);c.setDash()
def dot(x,y,col):
 c.setFillColor(HexColor(col));c.circle(x,H-y,2.3,fill=1,stroke=0)
start('4.0','Wire power and data','Recommended wiring: move boost input from the reported 3V connection to BAT. Power off before rework.')
box('LiPo 2011<br/>3.7 V nominal',28,89,123,50)
box('Feather 5000<br/>Battery JST socket',205,89,151,50)
wire([(151,110),(205,110)],'#754C24');text('JST plug',155,101,8,GRAY)
box('TMF002 boost<br/>IN+ / IN- → OUT+ / OUT-',425,89,258,50)
wire([(356,110),(425,110)],'#754C24');text('BAT → IN+',361,100,8)
text('USB-C → Feather only: programming and charging',28,167,10)
box('Feather D6',28,199,123,43);box('Stick 1 DIN',238,199,151,43);box('Stick 2 DIN',492,199,191,43)
wire([(151,220),(238,220)]);text('DATA →',170,211,9,BLUE)
wire([(389,220),(492,220)]);text('DOUT → DIN',403,211,9,BLUE)
wire([(554,139),(554,180),(705,180),(705,265),(310,265)],'#B34839')
wire([(310,265),(310,242)],'#B34839');wire([(588,265),(588,242)],'#B34839');dot(588,265,'#B34839')
text('BOOST OUT+ = measured 5 V → both stick 5V pads',292,283,9,'#B34839')
wire([(28,315),(683,315)],GRAY,True)
text('COMMON GND: Feather GND + boost IN- / OUT- + both stick GND pads',29,307,9,GRAY)
para('Recommended BAT-fed topology; input rework is pending. D6 connects directly to DIN; no extra level shifter or bulk capacitor is installed. For a more robust 5 V data interface, see the next page. Never connect boost OUT+ to Feather BAT, 3V or USB 5V.',28,336,658,9)
end()

start('4.0a','Feather ESP32-S2 pinout','Adafruit PrettyPins artwork. USB-C at the top; match the labels on your board.')
c.drawImage(str(ASSETS/'references/adafruit-feather-esp32-s2-pinout.png'),28,H-65-286,width=485,height=286,preserveAspectRatio=True,anchor='c',mask='auto')
text('Our connections',535,100,12,bold=True)
para('<b>VBAT / BAT</b><br/>Boost IN+<br/><br/><b>GND</b><br/>Common ground<br/><br/><b>D6 / GPIO6</b><br/>First stick DIN<br/><br/><b>USB-C</b><br/>Program and charge',535,120,150,10)
link('Artwork: Adafruit · full-size pinout and board reference','https://learn.adafruit.com/adafruit-esp32-s2-feather/pinouts',28,348,657)
link('CC BY-SA 3.0 · full page rendered to PNG; labels unchanged','https://creativecommons.org/licenses/by-sa/3.0/',28,362,657)
end()

start('4.0b','NeoPixel stick solder pads','Use the labels on your board to identify each connection.')
text('View the board reference',28,92,12,bold=True)
link('Adafruit NeoPixel Stick 1426: product page and photos','https://www.adafruit.com/product/1426',28,117,345)
para('Open the product page to view the rear / solder-side photograph. With the printed label upright, DOUT is at the left-hand end and DIN at the right-hand end. Verify the actual silkscreen before soldering.',28,159,345,11)
para('The two sticks receive power in parallel and data in sequence. Turning a stick around in the enclosure does not change which pad is DIN.',28,260,345,10)
text('Read the printed pad labels',420,92,12,bold=True)
para('<b>DIN</b><br/>Stick 1: connect to Feather D6.<br/>Stick 2: connect to stick 1 DOUT.<br/><br/><b>DOUT</b><br/>Stick 1: connect to stick 2 DIN.<br/>Stick 2: leave unconnected.<br/><br/><b>5VDC and GND</b><br/>Both sticks share regulated 5 V and common ground. Each end has two GND pads.',420,113,264,10)
link('www.adafruit.com/product/1426','https://www.adafruit.com/product/1426',28,360,657)
end()

start('4.0c','Removable LED harness: details pending','The installed JST connection lets the top plate unplug without dismantling the base.')
text('Service the top plate',28,88,13,bold=True)
steps([('1','Disconnect USB and battery power before unplugging the LED harness.'),('2','Support the top plate. Separate the connector by its housings, without pulling the wires.'),('3','Allow service slack and keep wires clear of screws and mating surfaces. Final routing and access photos are pending.')],w=321,y=108)
text('To complete after the design is finalized',375,88,12,bold=True)
para('<b>TBD: connector</b><br/>JST family, pitch, contact count, mating parts and purchase link.<br/><br/><b>TBD: pinout and harness</b><br/>Numbered mating-face drawing with latch orientation; wire colors, gauge, lengths and strain relief.<br/><br/><b>TBD: electrical checks</b><br/>Boost resistor photo, final signal-conditioning parts, load current, temperature and runtime. TPS61023 replacement remains untested.',375,108,308,10)
para('TBD is not a wiring instruction. The LED assembly requires 5 V, ground and data; connector cavity assignments are not yet recorded. See docs/wiring.md for the editable completion checklist.',28,330,655,9,GRAY)
end()

start('4.1','Recommended signal conditioning','These additional parts are not included in the enclosure’s current fit validation.')
box('Feather D6<br/>3.3 V data',28,98,126,55);box('74AHCT125<br/>5 V powered',197,98,142,55);box('300–500 Ω<br/>series resistor',382,98,126,55);box('Stick 1 DIN',551,98,133,55)
for a,b in [(154,197),(339,382),(508,551)]:wire([(a,125),(b,125)])
para('<b>74AHCT125, channel 1 (14-pin package)</b><br/>Pin 14 VCC → regulated 5 V; pin 7 → common GND.<br/>Pin 1 /OE → GND; pin 2 A → Feather D6.<br/>Pin 3 Y → resistor → first stick DIN.<br/>Add 0.1 µF decoupling at VCC/GND. Disable unused channels and tie unused inputs to defined levels; verify your exact device pinout.',28,185,315,10)
para('<b>Pixel power</b><br/>Adafruit recommends a 500–1000 µF capacitor across LED 5 V and GND. Use a voltage rating of at least 6.3 V and observe polarity. Place the series resistor near the first pixel.<br/><br/>Plan an insulated mounting location before adding these parts. Recheck enclosure clearance; do not leave bare circuitry against the battery.',382,185,302,10)
link('Adafruit NeoPixel best practices','https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices',28,345,310)
link('TI SN74AHCT125 pinout and decoupling','https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf',382,345,302)
end()

start('4.2','Measure before connecting the LEDs')
steps([('4.2','With battery and USB unplugged, check polarity and inspect every solder joint. Check for unintended shorts between supply and ground.'),('4.3','The installed TMF002 needed two voltage-selection resistors desoldered to change 12 V to 5 V. Identify them from instructions for your exact board revision before removal; positions are not documented here.'),('4.4','Keep the LED 5 V leads disconnected. Power the boost from Feather BAT and GND, then measure OUT+ against OUT-.'),('4.5','Proceed only when the output is approximately 5 V with correct polarity. Disconnect power again before joining the LED supply leads.')],w=365,y=83)
box('Multimeter<br/>DC volts',454,107,172,72)
wire([(470,179),(470,245)],'#B34839');wire([(609,179),(609,245)],GRAY)
text('Red probe',444,265,10,'#B34839');text('Black probe',571,265,10,GRAY)
text('OUT+',457,288,12,bold=True);text('OUT-',586,288,12,bold=True)
para('Do not use the Feather 3V regulator to power the boost. The boost is not a battery charger; the battery charges through the Feather.',422,319,262,9)
end()

assembly('5.0','Fit the Feather locating dowels',['Base assembly  ×1','2 × 6 mm dowels  ×2'],[('5.1','Test each dowel in the two small PCB locating holes, opposite the USB side.'),('5.2','The revised bores are nominally 2.2 mm. They should accept the 2 mm dowels without cracking the pads.'),('5.3','If loose, use a small amount of adhesive below the bearing surface. Keep the board removable and the pad tops clean.')],'dowels','Seated dowels project 1.8 mm above the PCB supports. Do not hammer dowels into the printed base.')
assembly('5.4','Mount the controller and frame',['Feather  ×1','Feather frame  ×1','M2 × 8 screws  ×2'],[('5.4','Fit the Feather over the dowels with USB-C facing the case opening.'),('5.5','For final mounting, connect the prepared battery plug before the frame blocks access. Keep all exposed connections insulated.'),('5.6','Seat the frame on its two opposite locating posts. Fit two M2 screws through the USB-side access wells; tighten gently.')],'feather','The frame clamps the PCB mounting pads. Check the 1.3 mm driver reaches both recessed heads without rubbing the wells.')
assembly('5.7','Seat the battery and boost',['Battery  ×1','Boost module  ×1','Soft insulating pad  ×1'],[('5.7','Place the boost on its insulating seat inside the small cradle. Keep joints and leads clear of the lid stop.'),('5.8','Place the battery in its bay on a 1 mm soft nonconductive pad. Do not compress or puncture the pouch.'),('5.9','Route the battery lead beside the bay and away from the inserts. Leave enough slack to open the lid without pulling a solder joint.')],'battery','Battery and boost use cradles and lid stops, not separate screw clamps. Actual wire bends and connector fit require checking.')

start('6.0','Install the firmware before closing the case')
steps([('6.1','Install CircuitPython for the Adafruit ESP32-S2 Feather. Follow the board’s runtime installation guide.'),('6.2','Copy settings.example.toml to a private location. Enter your 2.4 GHz Wi-Fi details and a unique OTA password.'),('6.3','Set LATITUDE, LONGITUDE and TIMEZONE in your private settings.toml. Defaults are San Francisco. For another location, change all three: quoted decimal degrees and an IANA timezone.'),('6.4','Install from the repository root. Tap RESET afterward to apply the USB configuration.')],w=337,y=90)
text('USB install',396,106,13,bold=True)
para('<font face="Courier" size="9">uv run scripts/device.py inspect<br/><br/>uv run scripts/device.py install<br/>  --settings /private/path/settings.toml</font>',396,124,289,10)
para('Run the install command on one line. On systems other than macOS, pass <font face="Courier">--volume /path/to/CIRCUITPY</font>. The installer verifies the board and copies files with readback checks.',396,218,289,10)
link('CircuitPython for the exact Feather board','https://circuitpython.org/board/adafruit_feather_esp32s2/',396,301,289)
link('Install uv on your computer','https://docs.astral.sh/uv/getting-started/installation/',396,324,289)
end()

start('6.5','Run the first lighting check')
steps([('6.5','Power the open assembly. Check the boost voltage under load and look for heating or unstable output. Start at low brightness.'),('6.6','Open http://halloween.local on the same local network. If name discovery fails, use http:// followed by the board IP from your router.'),('6.7','Disable Sunset schedule for this manual check. Select a solid color at 10–15% brightness; test red, green and blue.'),('6.8','Confirm all 16 pixels respond and the second stick follows the first. Re-enable the schedule when ready.')],w=365,y=87)
text('If nothing lights',427,106,13,bold=True)
para('Press BOOT if daytime sleep has turned off Wi-Fi and the website.<br/><br/>Check common ground, boost output and DIN/DOUT direction. If only one stick works, check the first DOUT to second DIN link.<br/><br/>For flicker or wrong colors, check power stability, GRB/RGB selection and the recommended level shifter.',427,126,257,10)
para('Higher brightness increases load. The converter’s continuous rating, enclosed temperature and battery runtime are not yet measured.',427,305,257,9,GRAY);end()
assembly('7.0','Close the enclosure',['Completed base  ×1','Completed lid  ×1','M3 × 8 screws  ×4'],[('7.1','Remove USB power and disconnect the battery before arranging wires or closing the case.'),('7.2','Check full USB plug insertion, free wire bends and battery clearance. Reconnect the battery only after routing is secure.'),('7.3','Match the lid orientation key. Lower the lid without force, then fit four M3 screws evenly. Stop if the seam will not close freely.')],'close','Do not use the screws to pull a fouling lid into place. No wire, pouch or solder joint should sit between bearing surfaces.')
start('7.4','Final checks and future changes')
steps([('7.4','Confirm USB charging access and the BOOT / RESET pinholes. Use a suitable blunt probe; do not force it.'),('7.5','Test saved settings after a reset. Check manual blackout, browser reconnect and operation without a computer attached.'),('7.6','Observe the first full sunset/sunrise cycle and monitor temperature during the intended use. Record battery runtime before relying on it.')],w=342,y=88)
text('Modify the native design',405,105,13,bold=True)
para('Open mechanical/cad/enclosure.solidcraft with its sibling part files and hardware folder intact.<br/><br/>Edit named sketches, driving dimensions and feature operations in the source part. Save it, update its link in the assembly and check mating features.<br/><br/>Regenerate affected STLs after every geometry change. Print files are derivatives; the organized native history remains the editable design.',405,125,278,10)
para('CAD and four STL exports are synchronized and digitally checked. Hardware qualification is in progress for v1.0.0; results remain unrecorded.',28,337,656,9,GRAY);end()

start('','Licenses and credits')
para('Copyright 2026 Halloween LEDs contributors. Original guide text and illustrations: <link href="https://creativecommons.org/licenses/by-sa/4.0/" color="'+BLUE+'">CC BY-SA 4.0</link>. Credit the contributors, link to the source and license, and identify changes when sharing adaptations.',28,83,656,10)
para('Original software: GPL-3.0-only. Hardware design sources and exports: CERN-OHL-S-2.0. See LICENSE.md and LICENSES/ in the source repository for the scope and full terms. Third-party assets retain their own terms.',28,147,656,10)
para('Feather pinout: Adafruit Industries; upstream design credited to Limor Fried/Ladyada. <link href="https://creativecommons.org/licenses/by-sa/3.0/" color="'+BLUE+'">CC BY-SA 3.0</link>. Full pinout page rendered to PNG; labels unchanged. Upstream notices are preserved in the source repository.',28,205,656,10)
para('NeoPixel Stick reference: <link href="https://www.adafruit.com/product/1426" color="'+BLUE+'">Adafruit product 1426</link>. Product photographs are available on Adafruit\'s website; they are not reproduced in this guide.',28,267,656,10)
para('Presentation inspired by <link href="https://www.curvlab.com/guides/wr1-build" color="'+BLUE+'">CURV LAB\'s WR1 Chassis Build Guide</link>. Assembly illustrations and instructions were created for Halloween LEDs. See THIRD_PARTY_NOTICES.md for source links and details.',28,326,656,9)
end()
c.save();print(f'{OUT} ({page} pages)')
