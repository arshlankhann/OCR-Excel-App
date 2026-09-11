import re
from utils.validation import format_vehicle_number

def extract_fields(text_blocks):
    rst_no = None
    vehicle_no = None
    net_weight = None
    agency_name = None
    
    full_text = " ".join(text_blocks).upper()
    
    rst_match = re.search(r'(?:RST|SLIP|AST)[A-Z\s\.:-]{0,15}?(?<![0-9OoSs])((?:[0-9OoSs]\s*){4})(?![0-9OoSs])', full_text)
    if rst_match:
        raw_rst = rst_match.group(1)
        rst_no = raw_rst.replace(' ', '').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
    else:
        top_text = " ".join(text_blocks[:10]).upper()
        matches = re.findall(r'(?<![0-9OoSs])((?:[0-9OoSs]\s*){4})(?![0-9OoSs])', top_text)
        for m in matches:
            val = m.replace(' ', '').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
            if val.startswith('20') and len(val) == 4:
                continue
            rst_no = val
            break
    
    # Vehicle No Logic
    # Strategy 1: Look directly after "VEHICLE NO"
    v_prefix_match = re.search(r'(?:VEHICLE\s*NO\.?|VEH\.?\s*NO\.?)\s*[:\-]?\s*([A-Z]{2}\s*\d{1,2}\s*[A-Z]{0,3}\s*\d{1,4})', full_text)
    if v_prefix_match:
        raw_v = v_prefix_match.group(1)
        vehicle_no = format_vehicle_number(raw_v.replace(" ", ""))
    else:
        # Strategy 2: Look for states likely in this region (HR, DL, UP, RJ, PB, CH, UK)
        region_pattern = r'\b(?:HR|DL|UP|RJ|PB|CH|UK)\s*\d{1,2}\s*[A-Z]{0,3}\s*\d{1,4}\b'
        region_matches = re.findall(region_pattern, full_text)
        if region_matches:
            vehicle_no = format_vehicle_number(region_matches[0].replace(" ", ""))
        else:
            # Strategy 3: Look for any standard 4-digit ending plate
            strict_pattern = r'\b[A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{4}\b'
            strict_matches = re.findall(strict_pattern, full_text)
            if strict_matches:
                vehicle_no = format_vehicle_number(strict_matches[0].replace(" ", ""))
            else:
                # Strategy 4: The fallback loose pattern
                loose_pattern = r'\b[A-Z]{2}\s*\d{1,2}\s*[A-Z]{0,3}\s*\d{1,4}\b'
                loose_matches = re.findall(loose_pattern, full_text)
                if loose_matches:
                    vehicle_no = format_vehicle_number(loose_matches[0].replace(" ", ""))
        
    # Net Weight Logic
    # Strategy 1: Mathematical Relationship (Gross - Tare = Net)
    all_num_strs = re.findall(r'(?<![0-9OoSs])((?:[0-9OoSs]\s*){4,5})(?![0-9OoSs])', full_text)
    parsed_nums = []
    for s in all_num_strs:
        clean = s.replace(' ', '').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
        if clean.startswith('20') and len(clean) == 4:
            continue
        try:
            parsed_nums.append(int(clean))
        except:
            pass
        
    for i in range(len(parsed_nums)):
        for j in range(len(parsed_nums)):
            if i == j: continue
            for k in range(len(parsed_nums)):
                if k == i or k == j: continue
                if parsed_nums[i] - parsed_nums[j] == parsed_nums[k] and parsed_nums[i] > parsed_nums[j]:
                    net_weight = str(parsed_nums[k])
                    break
            if net_weight: break
        if net_weight: break

    # Strategy 2: Regex and Block search
    if not net_weight:
        net_wt_match = re.search(r'(?:NET|N\s*E\s*T|HET|N\.E\.T\.?).{0,25}?(?<![0-9OoSs])((?:[0-9OoSs]\s*){4,5})(?![0-9OoSs])', full_text)
        
        if net_wt_match:
            raw_net = net_wt_match.group(1)
            net_weight = raw_net.replace(' ', '').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
        else:
            for i, block in enumerate(text_blocks):
                block_upper = block.upper()
                if "NET" in block_upper or "HET" in block_upper:
                    digits = re.findall(r'(?<![0-9OoSs])((?:[0-9OoSs]\s*){4,5})(?![0-9OoSs])', block_upper)
                    if digits:
                        net_weight = digits[-1].replace(' ', '').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
                        break
                    elif i + 1 < len(text_blocks):
                        digits = re.findall(r'(?<![0-9OoSs])((?:[0-9OoSs]\s*){4,5})(?![0-9OoSs])', text_blocks[i+1])
                        if digits:
                            net_weight = digits[-1].replace(' ', '').replace('O', '0').replace('o', '0').replace('S', '5').replace('s', '5')
                            break

    # Agency Name Extraction
    for block in text_blocks:
        b_up = block.upper()
        if "SVN" in b_up:
            agency_name = "SVN"
            break
        elif "J.P" in b_up or "JP" in b_up:
            agency_name = "J.P Bros"
            break
        elif "V S" in b_up or "VS" in b_up or "VS WASTE" in b_up:
            agency_name = "V S Waste"
            break
        elif "TRACTOR" in b_up:
            agency_name = "Tractor"
            break
        elif "MCF" in b_up or "GOV" in b_up or "GOVERNMENT" in b_up:
            agency_name = "Government"
            break

    return {
        "rst_no": rst_no,
        "vehicle_no": vehicle_no,
        "net_weight": net_weight,
        "agency_name": agency_name
    }
