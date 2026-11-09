from huaweicloud_mcp_core.server import run_standard
from mcp_server_supabase.server import mcp


def main():
    run_standard(mcp, service_name="supabase")


if __name__ == "__main__":
    main()
