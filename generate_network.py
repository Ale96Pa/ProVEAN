import os
import argparse

from progag.netgen import generate_model

# Make sure the network directory exists
if not os.path.exists('network'):
    os.makedirs('network')

parser = argparse.ArgumentParser()
parser.add_argument('--num_hosts', type=int,
                    default=100, help='Number of hosts')
parser.add_argument('--services_per_host', type=int,
                    default=2, help='Number of services per host')
parser.add_argument('--num_vulns_per_service', type=int,
                    default=2, help='Number of vulnerabilities per service')
parser.add_argument('--output_file', type=str,
                    default=None, help='Output file')
args = parser.parse_args()

if args.output_file:
    output_file_name = args.output_file
else:
    output_file_name = 'network/model_{}h_{}s_{}v.json'.format(
        args.num_hosts, args.services_per_host, args.num_vulns_per_service)

print("Generating network model with {} hosts, {} services per host, "
      "and {} vulnerabilities per service".format(
          args.num_hosts, args.services_per_host, args.num_vulns_per_service))

model = generate_model(
    args.num_hosts,
    min_services_per_host=args.services_per_host,
    max_services_per_host=args.services_per_host,
    min_vulns_per_service=args.num_vulns_per_service,
    max_vulns_per_service=args.num_vulns_per_service)

print("Saving model to {}".format(output_file_name))

model.save_to_file(output_file_name)
