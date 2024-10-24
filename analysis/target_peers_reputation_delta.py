import csv
import statistics

# Hardcoded target node number
TARGET_NODE = 22

FILE="ln_51_attacker_reputations.csv"

# Initialize a list to hold the channels of the target node
target_channels = []

# Read the reputations.csv file and extract channels for the target node
with open(FILE, "r") as csvfile:
    reader = csv.reader(csvfile)
    header = next(reader)  # Read the header row

    # First pass: Identify channels associated with the target node
    for row in reader:
        if int(row[0]) == TARGET_NODE:
            target_channels.append(int(row[1]))
            target_channels.append(int(row[2]))

# Deduplicate channels
target_channels = set(target_channels)

# Reopen the file to check for chan_out occurrences
with open(FILE, "r") as csvfile:
    reader = csv.reader(csvfile)
    header = next(reader)  # Skip the header again

    # Print rows where the target node is the chan_out
    reputation_values = []
    for row in reader:
        # We don't want the perspective of the target node, we want its outgoing rep with its peers.
        if int(row[0]) == TARGET_NODE:
            continue

        # Debug line to check each row's chan_out value
        if int(row[2]) in target_channels:
            revenue_in = float(row[4])
            reputation_out = float(row[5])

            if revenue_in < reputation_out:
                reputation_values.append(reputation_out - revenue_in)

print(f"count = {len(reputation_values)}")
print(f"sum = {sum(reputation_values)}")
print(f"average = {sum(reputation_values) / len(reputation_values)})")
print(f"minimum = {min(reputation_values)}")
print(f"maximum = {max(reputation_values)}")
print(f"median = {statistics.median(reputation_values)}")
