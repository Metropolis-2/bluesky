'''
Client to send unifly telemetry
'''
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit
import requests
import json
import codecs
import datetime
from datetime import timedelta
from time import sleep

# TODO: move requests outisde of client and maybe no need to disable telemetry
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
        self.subscribe(b'POSTUASOP')
        self.subscribe(b'POSTLANDING')
        self.subscribe(b'POSTTAKEOFF')
        self.subscribe(b'POSTNEWFLIGHTPLAN')

    def event(self, name, data, sender_id):
        ''' Overridden event function to handle incoming ECHO commands. '''
        pass

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

        elif name == b'POSTUASOP':
            cmdline.post_uas_op(data)

        elif name == b'POSTLANDING':
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

    def post_uas_op(self, data):

            acid = data.pop('acid')
            operator_token = data.pop('operator_token')
            base_url = data.pop('base_url')
            uuid = data.pop('uuid')

            console.rule(style='green', title=f'[bold blue]Posting UAS operation for aircraft with acid:[bold green] {acid}')
            print(f'[blue]Posting draft operation for acid: [green]{acid}[/] with uuid: [green]{uuid}')

            response = requests.request(**data)

            if response.status_code == 200:
                op_uuid = response.json()['uniqueIdentifier']
                print(f'[blue]Successfully posted draft operation for acid [green]{acid}[/] with operation id: [green]{op_uuid}')
            else:
                console.rule(style='red')
                print(f'[red]Failed to post draft operation for acid [green]{acid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')
                return
            # sleep for 2 seconds before Publishing the draft operation
            sleep(2)

            # The second step is to publish the draft operation
            print(f'[blue]Publishing UAS operation for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')

            # Prepare the message for publishing
            url = f"{base_url}/api/uasoperations/{op_uuid}/publish"
            payload = ""
            headers = {
            'Content-Type': 'application/vnd.geo+json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {operator_token}'
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            
            if response.status_code == 200:
                print(f'[blue]Successfully published operation for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')
            else:
                console.rule(style='red')
                print(f'[red]Failed to publish operation for acid: {acid} with operation id: [green]{op_uuid}')
                print(f'[red]Status Code: [cyan]{response.status_code}')
                print(response.json())
                console.rule(style='red')

            # sleep 2 seconds before requesting action items
            sleep(2)

            # The third step is to request action items
            print(f'[blue]Requesting action items for acid: [green]{acid}[/] witb operation id: [green]{op_uuid}')

            # Prepare the message for asking for action items
            url = f"{base_url}/api/uasoperations/{op_uuid}/actionItems"
            payload={}
            response = requests.request("GET", url, headers=headers, data=payload)

            # Check if you need to ask for permission
            if response.json()[0]['status'] == 'INITIATED' and response.json()[0]['type'] == 'PERMISSION':
                
                print(f'[blue]Requesting permission for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')

                # get the action unique id
                action_uid = response.json()[0]['uniqueIdentifier']

                # Prepare the permission request
                url = f"https://portal.eu.unifly.tech/api/uasoperations/{op_uuid}/permissions/{action_uid}/request"
                now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
                payload_key_meta = {
                'uniqueIdentifier': '{{'+action_uid+'}}',
                'additionalData': {},
                'permissionRemark': {
                    'message': {
                    'message': 'test',
                    'timestamp': now
                    }
                }
                }
                files = []
                boundary = 'wL36Yn8afVp8Ag7AmP8qZ0SA4n1v9T'
                dataList = []
                dataList.append(codecs.encode(f'--{boundary}'))
                dataList.append(codecs.encode('Content-Disposition: form-data; name=meta;'))
                dataList.append(codecs.encode('Content-Type: {}'.format('application/json')))
                dataList.append(codecs.encode(''))
                dataList.append(codecs.encode(json.dumps(payload_key_meta)))
                dataList.append(codecs.encode(f'--{boundary}--'))
                dataList.append(codecs.encode(''))
                payload = b'\r\n'.join(dataList)

                headers = {
                'Authorization': f'Bearer {operator_token}',
                'Content-type': f'multipart/form-data; boundary={boundary}'
                }
                response = requests.request("POST", url, headers=headers, data=payload, files=files)       

                if response.status_code == 201:
                    print(f'[blue]Successfully requested permission for acid: [green]{acid}[/] with operation id: [green]{op_uuid}') 
                    print(f'[bold blue]Aircraft with acid: [green]{acid}[/] is waiting for take off command.')
                    console.rule(style='green')

                else:
                    console.rule(style='red')
                    print(f'[red]Failed to request permission for acid: [green]{acid}[/] with operation id: [green]{op_uuid}')
                    print(f'[red]Status Code: [cyan]{response.status_code}')
                    print(response.json())
                    console.rule(style='red')

            # send the opid back to sim
            bsclient.stack(f'SETOPUID {acid} {op_uuid}')


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
