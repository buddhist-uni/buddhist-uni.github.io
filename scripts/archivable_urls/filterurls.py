import re

input_file = "urls.txt"
output_file = "filteredurls.txt"

# Regular expression patterns
archive_org = r"https?://(web\.)?archive\.org"
dropbox = r"https?://(www\.)?dropbox\.com"
include_pattern = r"(https?://(?!.*archive\.org)\S*?(\.html?|\.mp3|pdf)|https?://\S*?/(download|viewcontent.cgi)\S*|https?://(www\.)?accesstoinsight\.org|https?://(www\.)?dhammatalks\.org|https?://(www\.)?thezensite\.com|https?://(www\.)?bhantesuddhaso\.com)"

# Set to store unique URLs
unique_urls = set()

# Open the input file
with open(input_file, "r") as f_in:
    # Read each line from the input file
    for line in f_in:
        # Exclude URLs matching the exclude patterns
        if re.search(dropbox, line) or re.search(archive_org, line):
            continue

        # Find the URLs matching the include pattern
        match = re.search(include_pattern, line)
        if match:
            unique_urls.add(line.strip())

# Open the output file
with open(output_file, "w") as f_out:
    # Write the unique URLs to the output file
    for url in unique_urls:
        f_out.write(url + "\n")

print("Filtered URLs (with duplicates removed) extracted and saved to 'filteredurls.txt'.")
