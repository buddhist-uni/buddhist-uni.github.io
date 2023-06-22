import re

# download the latest lychee output from GitHub
input_file = "lycheeout.txt"
output_file = "urls.txt"

# Regular expression pattern to match the desired URLs
pattern = r"✔ \[200\] (https?://\S+)"

# Open the input and output files
with open(input_file, "r") as f_in, open(output_file, "w") as f_out:
    # Read each line from the input file
    for line in f_in:
        # Find the URLs matching the pattern
        match = re.search(pattern, line)
        if match:
            url = match.group(1)
            # Write the URL to the output file
            f_out.write(url + "\n")

print("URLs extracted and saved to 'urls.txt'.")
