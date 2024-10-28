import sys
import subprocess
import json

def run_lncli_command(command):
    result = subprocess.run(
        command.split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    if result.returncode != 0:
        print(f"Error running command {command}: {result.stderr.decode('utf-8')}")
        return None
    
    return json.loads(result.stdout.decode('utf-8'))

def get_peacetime_revenue(forwarding_hist_file, revenue_period_ns):
    success_fees_msat = 0
    uncond_fees_msat = 0
    timestamp_limit = None

    with open(forwarding_hist_file, 'r') as file:
        data = json.load(file)
        
    for forward in data['forwards']:
        incoming_amount = int(forward['incomingAmount'])
        outgoing_amount = int(forward['outgoingAmount'])
        fee_msat = incoming_amount - outgoing_amount
        incoming_add_ts = int(forward['addTimeNs'])

        # We want to only get entries for the period that we've defined to have a way to compare revenue to what we got in the simulation 
        # that ran for revenue_period_ns. We don't have a start time for this projected data, so we just grab our first timestamp as the 
        # start. This is imperfect, and may lead to us over-estimating revenue without an attack (especially if there was a long wait 
        # for the first payment to occur). This could possibly be improved by including the start time in the file name so we can get 
        # an exact start, but is okay for now.
        # 
        # We can't use actual timestamps here, because this data was generated once-off and has old timestamps (hasn't been "progressed"
        # to current times like we do for bootstrapped data, as this isn't actually necessary).
        if timestamp_limit is None:
            timestamp_limit = incoming_add_ts + revenue_period_ns

        if incoming_add_ts >= timestamp_limit:
            break
           
        if forward['settled']:
            success_fees_msat += fee_msat
        else:
            uncond_fees_msat += fee_msat*0.01

    return success_fees_msat, uncond_fees_msat

def get_target_revenue(forwarding_hist_file, start_time_ns, end_time_ns):
    with open(forwarding_hist_file, 'r') as file:
        data = json.load(file)
        
    success_fee_msat = 0
    unconditional_fee_msat = 0

    for forward in data['forwards']:
        # If incoming/ outgoing match, it's bootstrapped
        htlcIn = forward['incomingCircuit']['htlcIndex']
        htlcOut = forward['outgoingCircuit']['htlcIndex']
        if htlcIn == htlcOut and int(htlcIn) > 4294967295:
            continue

        resolveTime = int(forward['resolveTimeNs'])
        if resolveTime < start_time_ns:
            continue

        if resolveTime > end_time_ns:
            continue
        
        incoming_amount = int(forward['incomingAmount'])
        outgoing_amount = int(forward['outgoingAmount'])
        fee_msat = incoming_amount - outgoing_amount

        if forward['settled']:
            success_fee_msat += fee_msat

        unconditional_fee_msat += fee_msat * 0.01

    return success_fee_msat, unconditional_fee_msat

def paginate_lncli_listpayments(command, max_payments_per_call=10):
    index_offset = 0
    all_payments = []
    
    while True:
        response = run_lncli_command(f"{command} listpayments --include_incomplete --paginate_forwards --index_offset={index_offset} --max_payments={max_payments_per_call}")

        if response is None:
            break
        
        payments = response.get('payments', [])
        all_payments.extend(payments)

        last_index_offset = response.get('last_index_offset', 0)
        num_payments_returned = len(payments)
        
        if num_payments_returned < max_payments_per_call:
            break
        
        # Prepare for the next call
        index_offset = last_index_offset
    
    return all_payments


def process_attacker_payments(payments, target_pubkey, start_time_ns, end_time_ns):
    results = []

    attacker_total = 0
    attacker_success_msat = 0
    attacker_unconditional_msat = 0

    target_total = 0
    target_success_msat = 0
    target_unconditional_msat = 0

    for payment in payments:
        creation_time_ns = int(payment.get("creation_time_ns", 0))
        if start_time_ns <= creation_time_ns <= end_time_ns:
            attacker_total += 1
            for htlc in payment["htlcs"]:
                    attacker_total += 1
                    success = htlc["status"] == "SUCCEEDED"
                
                    route_fee = int(htlc["route"]["total_fees_msat"])
                    attacker_unconditional_msat += route_fee
                
                    if success:
                        attacker_success_msat += route_fee

                    for hop in htlc["route"]["hops"]:
                        if hop["pub_key"] == target_pubkey:
                            target_total += 1
                            hop_fee_msat = int(hop["fee_msat"])

                            target_unconditional_msat += hop_fee_msat
                            if success:
                                target_success_msat += hop_fee_msat

    return {
        'attacker_total': attacker_total,
        'attacker_success_msat': attacker_success_msat,
        'attacker_unconditional_msat': attacker_unconditional_msat * 0.01,
        'target_total': target_total,
        'target_success_msat': target_success_msat,
        'target_unconditional_msat': target_unconditional_msat * 0.01,
    }

def get_attacker_costs(file_name, command, target_pubkey, start_time_ns, end_time_ns, max_payments_per_call=10000):
    result = paginate_lncli_listpayments(command, max_payments_per_call)
   
    # Write to json file so that we can re-run if necessary.
    with open(file_name, 'w') as f:
        json.dump({"payments": result}, f, indent=4)

    return process_attacker_payments(result, target_pubkey, start_time_ns, end_time_ns)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python projected_revenue.py <network_name> <start_ns> <end_ns>") 
        sys.exit(1)

    network_name = sys.argv[1]
    start_time_ns = int(sys.argv[2])
    end_time_ns = int(sys.argv[3]) 

    projection_file=f"data/{network_name}/projections/forwarding_history.json"
    success, uncond = get_peacetime_revenue(projection_file, end_time_ns - start_time_ns)
    print(f"Revenue {success+uncond} msat for {network_name} duration {end_time_ns - start_time_ns}")
