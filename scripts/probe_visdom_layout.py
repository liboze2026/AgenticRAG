"""Probe VisDoM-main remote dir to discover query/gold JSON layout."""
import os
import re
import sys
import paramiko
import yaml
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _resolve_env(value: str) -> str:
    if not isinstance(value, str):
        return value
    pattern = re.compile(r"\$\{(\w+)\}")
    return pattern.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def listdir(sftp, path):
    try:
        return sftp.listdir(path)
    except Exception as e:
        return [f"<error: {e}>"]


def main():
    cfg = yaml.safe_load(open("config/default.yaml", encoding="utf-8"))
    server = cfg["ssh_servers"][0]
    pwd = _resolve_env(server.get("target_password", "")) or os.environ.get("SSH_PRIMARY_PASSWORD", "")
    transport = paramiko.Transport((server["target_host"], server["target_port"]))
    transport.connect(username=server["target_user"], password=pwd)
    sftp = paramiko.SFTPClient.from_transport(transport)

    root = server["deployment"]["visdom_data"]
    subsets = ["feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa"]
    for s in subsets:
        d = f"{root}/{s}"
        contents = listdir(sftp, d)
        print(f"\n=== {s} ===")
        print(f"  files: {contents[:30]}")
        # Recurse one level for any sub-dirs
        for item in contents[:15]:
            sub = f"{d}/{item}"
            try:
                inner = sftp.listdir(sub)
                print(f"    {item}/ → {inner[:10]}{'…' if len(inner) > 10 else ''}")
            except Exception:
                pass
        # Try peek one .json/.jsonl
        for item in contents:
            if item.endswith((".json", ".jsonl", ".csv")):
                p = f"{d}/{item}"
                try:
                    with sftp.open(p) as f:
                        head = f.read(800).decode("utf-8", errors="replace")
                    print(f"  --- head of {item} ({p}) ---")
                    print(head[:600])
                except Exception as e:
                    print(f"    read {p} failed: {e}")
                break

    sftp.close()
    transport.close()


if __name__ == "__main__":
    main()
