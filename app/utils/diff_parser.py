# app/utils/diff_parser.py

def annotate_diff(raw_diff: str) -> str:
    """
    Parses a raw git diff and prepends the actual file line numbers in brackets 
    [X] to the added (+) and context ( ) lines.
    """
    annotated_lines = []
    new_line_num = 0
    
    for line in raw_diff.split('\n'):
        if line.startswith('+++ b/'):
            annotated_lines.append(line)
        elif line.startswith('@@ '):
            # Parse the hunk header: @@ -1,5 +10,8 @@
            # We want the '10', which is the starting line of the new code
            try:
                plus_part = line.split('+')[1].split(' ')[0]
                new_line_num = int(plus_part.split(',')[0])
            except (IndexError, ValueError):
                pass
            annotated_lines.append(line)
        elif line.startswith('+') and not line.startswith('+++'):
            # Added line
            annotated_lines.append(f"[{new_line_num}] {line}")
            new_line_num += 1
        elif line.startswith(' '):
            # Unchanged context line
            annotated_lines.append(f"[{new_line_num}] {line}")
            new_line_num += 1
        else:
            # Removed line (-) or other diff metadata
            annotated_lines.append(line)
            
    return '\n'.join(annotated_lines)