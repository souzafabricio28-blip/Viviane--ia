import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from interface_darkson import DarksonApp

app = DarksonApp()
try:
    app.mainloop()
except KeyboardInterrupt:
    app.parar()
