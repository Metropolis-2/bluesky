'''
Client to send unifly telemetry
'''
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit
import requests
import json
try:
    from rich import print
    from rich.console import Console

except ImportError:
    class Console:
        def rule(self, style=None, title=None, **kwargs):
            print(title)

from bluesky.network.client import Client


# The echo textbox, command line, and bluesky network client as globals
echobox = None
cmdline = None
bsclient = None
console = Console()


class TextClient(Client):
    '''
        Subclassed Client with a timer to periodically check for incoming data,
        an overridden event function to handle data, and a stack function to
        send stack commands to BlueSky.
    '''
    def __init__(self, actnode_topics=b''):
        super().__init__(actnode_topics=b'')
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(20)

        self.subscribe(b'POSTTELEMETRY')
        self.subscribe(b'POSTGAFLIGHT')

    def event(self, name, data, sender_id):
        ''' Overridden event function to handle incoming ECHO commands. '''

        if name == b'POSTLANDING':
            # remove acid from data
            acid = data.pop('acid')
            response = requests.request(**data)
            if response.status_code == 200:
                print(f'[blue]Successfully posted landing for aircraft with acid: [green]{acid}[/]')
            else:
                console.rule(style='red')
                print(f'[red]Failed to post landing for aircraft with acid: [green]{acid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')
                return

        elif name == b'POSTTAKEOFF':
            # remove acid from data
            acid = data.pop('acid')
            response = requests.request(**data)
            if response.status_code == 200:
                print(f'[blue]Successfully posted takeoff for aircraft with acid: [green]{acid}[/]')
            else:
                console.rule(style='red')
                print(f'[red]Failed to post takeoff for aircraft with acid: [green]{acid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')
                return

        elif name == b'POSTNEWFLIGHTPLAN':
            # remove acid and other info from data
            acid = data.pop('acid')
            uuid = data.pop('uuid')
            opuid = data.pop('opuid')

            console.rule(style='green', title=f'[bold blue]Posting modified UAS operation for aircraft with acid:[bold green] {acid}')
            print(f'[blue]Posting modified operation for acid: [green]{acid}[/] with uuid: [green]{uuid}')
            
            # send request
            response = requests.request(**data)

            if response.status_code == 200:
                print(f'[blue]Successfully posted modified operation for acid [green]{acid}[/] with operation id: [green]{opuid}')
            else:
                console.rule(style='red')
                print(f'[red]Failed to post modified operation for acid [green]{acid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')
                return
            
            console.rule(style='green')

    def stream(self, name, data, sender_id):

        if name == b'POSTTELEMETRY':

            for acid, request_dict in data.items():
                # send request
                response = requests.request(**request_dict)
                if response.status_code == 200:
                    print(f'[bright_black]Posting telemetry for aircraft with acid: [green]{acid}[/]')
                else:
                    console.rule(style='red')
                    print(f'[red]Failed to post telemetry for aircraft with acid: [green]{acid}')
                    print(f'[red]Status Code: [cyan]{response.status_code}')
                    print(response.json())
                    console.rule(style='red')
        
        elif name == b'POSTGAFLIGHT':
            for acid, request_dict in data:
                # send request
                response = requests.request(**request_dict)
                print(f'[blue]Sending general aviation data for aircraft with acid: [green]{acid}[/]')

    def stack(self, text):
        ''' Stack function to send stack commands to BlueSky. '''
        self.send_event(b'STACK', text)


class Echobox(QTextEdit):
    ''' Text box to show echoed text coming from BlueSky. '''
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.NoFocus)

    def echo(self, text, flags=None):
        ''' Add text to this echo box. '''
        self.append(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class Cmdline(QTextEdit):
    ''' Wrapper class for the command line. '''
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(21)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        ''' Handle Enter keypress to send a command to BlueSky. '''
        if event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
            if bsclient is not None:
                bsclient.stack(self.toPlainText())
                echobox.echo(self.toPlainText())
            self.setText('')
        else:
            super().keyPressEvent(event)


if __name__ == '__main__':
    # Construct the Qt main object
    app = QApplication([])

    # Create a window with a stack text box and a command line
    win = QWidget()
    win.setWindowTitle('Example external client for BlueSky')
    layout = QVBoxLayout()
    win.setLayout(layout)

    echobox = Echobox(win)
    cmdline = Cmdline(win)
    layout.addWidget(echobox)
    layout.addWidget(cmdline)
    win.show()

    # Create and start BlueSky client
    bsclient = TextClient()
    bsclient.connect(event_port=11000, stream_port=11001)

    # Start the Qt main loop
    app.exec_()
