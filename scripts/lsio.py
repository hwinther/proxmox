#!/usr/bin/python3
"""

lsio 0.4.0
Hans Christian Winther-Sorensen

Usage: python lsio.py minimal [remote command]
Examples:

> Full output (local machine)
# python lsio.py

> Minimal output (local machine)
# python lsio.py minimal

> Minimal output (remote machine)
# python lsio.py minimal ssh -l root other-machine

Requirements:
nvme - apt install nvme-cli

"""
import os
import argparse
import codecs
import json

__black = u'\u001b[30m'
__red = u'\u001b[31m'
__green = u'\u001b[32m'
__yellow = u'\u001b[33m'
__blue = u'\u001b[34m'
__magenta = u'\u001b[35m'
__cyan = u'\u001b[36m'
__white = u'\u001b[37m'
__reset = u'\u001b[0m'
cmd_prefix = ''


def success(text):
    print('%s%s%s' % (__green, text, __reset))


def info(text):
    print('%s%s%s' % (__blue, text, __reset))


def notice(text):
    print('%s%s%s' % (__cyan, text, __reset))


def warn(text):
    print('%s%s%s' % (__yellow, text, __reset))


def error(text):
    print('%s%s%s' % (__red, text, __reset))


def debug(text):
    print('%s%s%s' % (__magenta, text, __reset))


def system_output(cmd, temp_file_name):
    global cmd_prefix
    os.system('%s%s > %s' % (cmd_prefix, cmd, temp_file_name))
    content = codecs.open(temp_file_name, 'r', 'utf-8').read()
    os.remove(temp_file_name)
    return content


def parse_iommu_groups():
    """
    find /sys/kernel/iommu_groups/ -type l
    /sys/kernel/iommu_groups/7/devices/0000:00:1b.4
    """
    group_table = {}
    device_table = {}
    iommu_temp_file = '/tmp/iommu.tmp'
    content = system_output('find /sys/kernel/iommu_groups/ -type l', iommu_temp_file)
    for line in content.split('\n'):
        if line == '':
            continue
        group, device = line.replace('/sys/kernel/iommu_groups/', '').split('/devices/', 1)
        if group not in group_table:
            group_table[group] = []
        group_table[group].append(device)
        device_table[device] = group
    return group_table, device_table


def parse_lspci(verbose):
    device_table = {}
    lspci_temp_file = '/tmp/lspci.tmp'
    content = system_output('lspci -vvvq', lspci_temp_file)
    sections = content.replace('\n\n\t\t', '\n\t\t').split('\n\n')
    if '' in sections:
        sections.remove('')
    for section in sections:
        if section == '':
            continue
        lines = section.split('\n')
        basic_info = lines[0].split(' ', 1)
        address = basic_info[0]
        category, description = basic_info[1].split(': ', 1)
        if verbose:
            print('Address: %s' % address)
            print('Category: %s' % category)
            print('Description: %s' % description)
        attributes = {}
        capability = None
        status = None
        for line in lines[1:]:
            if line == '':
                continue
            if line.startswith('\t\t'):
                if line.find('LnkCap:\t') != -1:
                    capability = {}
                    for item in line.split('LnkCap:\t', 1)[1].split(', '):
                        if item == '':
                            continue
                        key, value = item.split(' ', 1)
                        capability[key] = value
                elif line.find('LnkSta:\t') != -1:
                    status = {}
                    for item in line.split('LnkSta:\t', 1)[1].split(', '):
                        if item == '':
                            continue
                        key, value = item.split(' ', 1)
                        status[key] = value
                continue
            if line.find('Expansion ROM at ') != -1:
                rom_data = line.split('Expansion ROM at ', 1)[1].split(' ')
                rom = {'address': rom_data[0], 'info': [x[1:-1] for x in rom_data[1:]]}
                attributes['rom'] = rom
                continue
            section_name, section_value = line.replace('\t', '').split(': ', 1)
            if section_name not in attributes:
                attributes[section_name] = []
            attributes[section_name].append(section_value)
        device_table[address] = {'category': category, 'description': description, 'capability': capability,
                                 'status': status, 'attributes': attributes}
        if verbose:
            if capability and status:
                print('Link capability: %s' % capability)
                print('Link status:     %s' % status)
            if 'Kernel driver in use' in attributes:
                print('Kernel driver: %s' % attributes['Kernel driver in use'][0])
            print('')
    return device_table


def parse_dmidecode(dmi_type, associative_key=None):
    parsed_data = []
    if associative_key:
        parsed_data = {}
    dmidecode_temp_file = '/tmp/dmidecode.tmp'
    content = system_output('dmidecode --type %s' % dmi_type, dmidecode_temp_file)
    sections = content.split('\n\n')
    if '' in sections:
        sections.remove('')
    if len(sections) == 0:
        return parsed_data
    if sections[0][0] == '#':
        sections.remove(sections[0])
    for section in sections:
        data = {}
        for line in section.split('\n'):
            if line == '':
                continue
            if not line.startswith('\t') and line.find(',') != -1:
                # ignoring the last entry, bytes
                for entry in line.split(', ')[:-1]:
                    entry = entry.rsplit(' ', 1)
                    data[entry[0]] = entry[1]
            elif line.startswith('\t') and not line.startswith('\t\t') and line.find(': ') != -1:
                key, value = line[1:].split(': ', 1)
                data[key] = value
        if associative_key:
            if associative_key in data:
                parsed_data[data[associative_key]] = data
        else:
            parsed_data.append(data)
    return parsed_data


def parse_lsblk():
    parsed_data = {}
    nvme_temp_file = '/tmp/lsblk.tmp'
    content = system_output('lsblk -pd -e7,259 -J', nvme_temp_file)
    for disk in json.loads(content)['blockdevices']:
        parsed_data[disk['name']] = disk
    return parsed_data


def parse_nvme():
    parsed_data = {}
    nvme_temp_file = '/tmp/nvme.tmp'
    content = system_output('nvme list -o json', nvme_temp_file)
    for device in json.loads(content)['Devices']:
        device_path = device['DevicePath']
        device_data = system_output('nvme smart-log %s -o json' % device_path, nvme_temp_file)
        parsed_data[device_path] = json.loads(device_data)
    return parsed_data


def parse_size_mb(size):
    if size.endswith('GB'):
        return int(size.split(' ')[0]) * 1024
    elif size.endswith('MB'):
        return int(size.split(' ')[0])
    else:
        error('Unknown size format: %s' % size)
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pci', metavar='all|issues|min|none|search phrase', help='list pci devices', default='all')
    parser.add_argument('--prefix', metavar='command', help='e.g. ssh -l root hostname', default=None)
    parser.add_argument('--verbose', dest='verbose', action='store_true')
    parser.add_argument('--quiet', dest='verbose', action='store_false')
    parser.set_defaults(verbose=False)
    args = parser.parse_args()

    if args.prefix is not None:
        global cmd_prefix
        cmd_prefix = args.prefix + ' '
        if args.verbose:
            info('Using prefix: %s' % cmd_prefix)

    iommu_group_table, iommu_device_table = parse_iommu_groups()
    dmidecode_device_table = parse_dmidecode('9', 'Bus Address')
    dmidecode_motherboard = parse_dmidecode('2')
    dmidecode_cpu = parse_dmidecode('4')
    dmidecode_memory_array = parse_dmidecode('16')
    dmidecode_memory_devices = parse_dmidecode('17')
    lspci_device_table = parse_lspci(args.verbose)
    lsblk_device_table = parse_lsblk()
    nvme_device_table = parse_nvme()

    dmi_reverse_table = {}
    if args.verbose:
        info('PCI devices: %d' % len(lspci_device_table))
    for address, pci in sorted(lspci_device_table.items()):
        short_address = address.split(':')[0]

        iommu = None
        for iommu_key, iommu_value in iommu_device_table.items():
            if iommu_key.split(':', 1)[1] == address:
                iommu = iommu_value
                break

        dmi = None
        for dmi_key, dmi_value in dmidecode_device_table.items():
            if dmi_key.split(':')[1] == short_address:
                dmi = dmi_value
                dmi_reverse_table[dmi_key] = pci
                break
        if dmi is None and False:
            warn('Attempting alternate DMI join for %s' % short_address)
            # print('%d/%d' % (len(dmi_reverse_table), len(dmidecode_device_table)))
            for dmi_key, dmi_value in dmidecode_device_table.items():
                if dmi_key not in dmi_reverse_table:
                    # if dmi_key.split(':')[2].split('.')[0] == short_address:
                    dmi = dmi_value
                    dmi_reverse_table[dmi_key] = pci
                    break

        capability = pci['capability']
        status = pci['status']

        if args.pci == 'none':
            continue
        elif args.pci == 'min':
            if pci['category'].find(' bridge') != -1 or pci['category'].find(' peripheral') != -1 or \
                    pci['category'] == 'SMBus' or pci['category'].find(' counters') != -1:
                continue
        elif args.pci == 'issues':
            if not capability or not status or capability['Speed'] == status['Speed']:
                continue
        elif args.pci != 'all':
            # limit the output with the value as a search phrase
            if pci['category'].lower().find(args.pci.lower()) == -1 and \
                    pci['category'].lower().find(args.pci.lower()) == -1:
                continue

        success('Address: %s%s' % (__white, address))
        if 'Kernel driver in use' in pci['attributes']:
            kernel_drivers = ', '.join(pci['attributes']['Kernel driver in use'])
            notice('\tCategory: %s%s %sDescription: %s%s %sKernel driver(s): %s%s' % (__green, pci['category'], __cyan,
                                                                                      __green, pci['description'],
                                                                                      __cyan, __green, kernel_drivers))
        else:
            notice('\tCategory: %s%s %sDescription: %s%s' % (__green, pci['category'], __cyan, __green,
                                                             pci['description']))

        if capability and status:
            if capability['Speed'] != status['Speed']:
                warn('\tCapability: %s%s%s@%s%s %sStatus: %s%s%s@%s%s' % (__red, capability['Speed'], __yellow, __red,
                                                                          capability['Width'], __yellow, __red,
                                                                          status['Speed'], __yellow, __red,
                                                                          status['Width']))
            else:
                notice('\tCapability: %s%s%s@%s%s %sStatus: %s%s%s@%s%s' % (__green, capability['Speed'], __cyan,
                                                                            __green, capability['Width'], __cyan,
                                                                            __green, status['Speed'], __cyan, __green,
                                                                            status['Width']))

        if iommu is not None:
            notice('\tIOMMU group: %s%s' % (__green, iommu))
        elif args.verbose:
            debug('Could not find IOMMU matching %s' % short_address)
            debug(iommu_device_table.keys())

        if dmi is not None:
            notice('\tDMI: %s%s (%s)' % (__green, dmi['Type'], dmi['Designation']))
        elif args.verbose:
            debug('Could not find DMI matching %s' % short_address)
            debug(dmidecode_device_table.keys())

        print('')

    mobo_manuf = 'n/a'
    mobo_name = 'n/a'
    if len(dmidecode_motherboard) >= 1:
        mobo_manuf = dmidecode_motherboard[0]['Manufacturer']
        mobo_name = dmidecode_motherboard[0]['Product Name']
    success('Motherboard %s%s %s%s' % (__cyan, mobo_name, __yellow, mobo_manuf))

    if len(dmidecode_cpu) >= 1:
        cpu_socket = dmidecode_cpu[0]['Socket Designation']
        cpu_version = dmidecode_cpu[0]['Version'].strip()
        cpu_core = dmidecode_cpu[0]['Core Count']
        cpu_threads = dmidecode_cpu[0]['Thread Count']
        cpu_voltage = dmidecode_cpu[0]['Voltage']
        cpu_current_speed = dmidecode_cpu[0]['Current Speed']
        cpu_max_speed = dmidecode_cpu[0]['Max Speed']
        success('CPU[1/%d] Socket: %s%s %sCore/Threads: %s%s/%s %sVersion: %s%s %sVoltage: %s%s %sCurrent/Max speed: '
                '%s%s/%s' % (len(dmidecode_cpu), __cyan, cpu_socket, __green, __cyan, cpu_core, cpu_threads, __green,
                             __cyan, cpu_version, __green, __cyan, cpu_voltage, __green, __cyan, cpu_current_speed,
                             cpu_max_speed))

    for memory_array in dmidecode_memory_array:
        memory_handle = memory_array['Handle']
        related_devices = []
        total_size_mb = 0
        active_devices = 0
        for memory_device in dmidecode_memory_devices:
            if memory_device['Array Handle'] == memory_handle:
                related_devices.append(memory_device)
                size = memory_device['Size']
                if size == 'No Module Installed':
                    continue
                active_devices += 1
                total_size_mb += parse_size_mb(size)
        success('Memory array: %s%s %sDevices: %s%d/%s %sCapacity: %s%s/%s' % (__cyan, memory_handle, __green, __cyan,
                                                                               active_devices,
                                                                               memory_array['Number Of Devices'],
                                                                               __green, __cyan, total_size_mb // 1024,
                                                                               memory_array['Maximum Capacity']))
        for memory_device in related_devices:
            size = memory_device['Size']
            if size == 'No Module Installed':
                notice('\tLocator: %s%s %s%s' % (__yellow, memory_device['Locator'], __magenta, size))
            else:
                size_mb = parse_size_mb(size)
                if 'Configured Memory Speed' not in memory_device:
                    notice(
                        '\tLocator: %s%s %sSize: %s%s GB %sType: %s%s %sManufacturer: %s%s %sPart #: '
                        '%s%s' % (__yellow, memory_device['Locator'],
                                  __cyan, __yellow, size_mb // 1024,
                                  __cyan, __yellow, memory_device['Type'],
                                  __cyan, __yellow, memory_device['Manufacturer'],
                                  __cyan, __yellow, memory_device['Part Number']))
                else:
                    notice(
                        '\tLocator: %s%s %sSize: %s%s GB %sSpeed %s%s @ %s %sType: %s%s %sManufacturer: %s%s %sPart #: '
                        '%s%s' % (__yellow, memory_device['Locator'],
                                  __cyan, __yellow, size_mb // 1024,
                                  __cyan, __yellow, memory_device['Configured Memory Speed'], memory_device['Speed'],
                                  __cyan, __yellow, memory_device['Type'],
                                  __cyan, __yellow, memory_device['Manufacturer'],
                                  __cyan, __yellow, memory_device['Part Number']))

    success('PCI slots:')
    for key, dmi in sorted(dmidecode_device_table.items(), key=lambda kv: kv[1]['Handle']):
        if dmi['Current Usage'] == 'Available':
            notice('\tEmpty slot: %s%s (%s)' % (__green, dmi['Type'], dmi['Designation']))
        elif key not in dmi_reverse_table:
            if args.verbose:
                error('Could not find DMI key %s in dmi_reverse_table' % key)
                print(dmi_reverse_table.keys())
                print(dmi)
        else:
            pci = dmi_reverse_table[key]
            if 'Kernel driver in use' in pci['attributes']:
                kernel_drivers = ', '.join(pci['attributes']['Kernel driver in use'])
                notice('\tUsed slot: %s%s (%s) %sCategory: %s%s %sDescription: %s%s %sKernel driver(s): %s%s' % (
                    __green, dmi['Type'], dmi['Designation'], __cyan, __green, pci['category'], __cyan, __green,
                    pci['description'], __cyan, __green, kernel_drivers))
            else:
                notice('\tUsed slot: %s%s (%s) %sCategory: %s%s %sDescription: %s%s' % (
                    __green, dmi['Type'], dmi['Designation'], __cyan, __green, pci['category'], __cyan, __green,
                    pci['description']))

    success('Disks:')
    for key, disk in lsblk_device_table.items():
        notice('\tDisk: %s%s Size: %s%s%%' % (__green, key, __cyan, disk['size']))
    for key, nvme in nvme_device_table.items():
        if nvme['percent_used'] <= 50:
            notice('\tNVME: %s%s Used: %s%d%%' % (__green, key, __cyan, nvme['percent_used']))
        else:
            notice('\tNVME: %s%s Used: %s%d%%' % (__green, key, __red, nvme['percent_used']))


if __name__ == '__main__':
    main()
