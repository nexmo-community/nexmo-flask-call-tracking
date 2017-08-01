import os
import json
from flask import Flask, request, jsonify
from tinydb import TinyDB, Query
import nexmo
from mixpanel import Mixpanel

app = Flask(__name__)
db = TinyDB('campaigns.json')

def get_campaign(number_to):
    Campaign = Query()
    campaigns = db.search(
        (Campaign.inbound_number == number_to) | (Campaign.redirect_number == number_to)
    )
    return campaigns[0] if campaigns else None

@app.route('/')
def answer():
    number_to = request.args.get('to')
    campaign = get_campaign(number_to)
    
    if campaign:
        ncco = [
            {
                'action': 'stream',
                'streamUrl': ['https://nexmo-calltracking.ngrok.io{message}'.format(
                    message=campaign['welcome_message']
                )]
            },
            {
                'action': 'record',
                'eventUrl': ['https://nexmo-calltracking.ngrok.io/record/']
            },
            {
                'action': 'connect',
                'from': campaign['inbound_number'],
                'endpoint': [{
                    'type': 'phone',
                    'number': campaign['redirect_number']
                }]
            }
        ]
        return jsonify(ncco)
    else:
        return jsonify([{
            'action': 'talk',
            'text': 'The number dialled has not been recognised. Please check and try again'
        }])

@app.route('/event', methods=['POST'])
def callevent():
    event = json.loads(request.data)

    if event['status'] == 'completed':
        campaign = get_campaign(event['to'])

        if campaign:
            mix = Mixpanel(os.environ['MIXPANEL_TOKEN'])
            client = nexmo.Client(
                key=os.environ['NEXMO_API_KEY'],
                secret=os.environ['NEXMO_API_SECRET']
            )

            # Fetch people data
            insight = client.get_advanced_number_insight(number=event['from'])
            uid = event['from']

            # Create/Update user in Mixpanel
            mix.people_set(
                uid,
                {
                    '$phone': '+' + event['from'],
                    '$first_name': insight.get('first_name'),
                    '$last_name': insight.get('last_name'),
                    'Country': insight.get('country_name'),
                    'Country Code': insight.get('country_code_iso3'),
                    'Valid Number': insight.get('valid_number'),
                    'Reachable': insight.get('reachable'),
                    'Ported': insight.get('ported'),
                    'Roaming': insight.get('roaming').get('status'),
                    'Carrier Name': insight.get('current_carrier').get('name'),
                    'Network Type': insight.get('current_carrier').get('network_type'),
                    'Network Country': insight.get('current_carrier').get('country'),
                }
            )
        
            # Track call data in Mixpanel
            mix.track(
                uid,
                'Inbound Call',
                {
                    'Campaign Name': campaign['name'],
                    'Duration': int(data.get('duration')),
                    'Start Time': data.get('start_time'),
                    'End Time': data.get('end_time'),
                    'Cost': float(data.get('price'))
                }
            )

            # Useful for Mixpanel revenue tracking
            mix.people_track_charge(uid, float(data.get('price')) * -1)

            # Track number of times user calls
            mix.people_increment(uid, {'Number of Calls': 1})

    return 'DONE'
