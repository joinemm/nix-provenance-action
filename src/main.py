import argparse
import json
import logging
import os
import subprocess
from datetime import datetime, timezone

LOG = logging.getLogger(os.path.abspath(__file__))


def exec_cmd(
    cmd: list[str],
    raise_on_error: bool = True,
    loglevel: int = logging.DEBUG,
):
    """Run shell command cmd"""
    command_str = " ".join(cmd)
    LOG.log(loglevel, "Running: %s", command_str)
    try:
        return subprocess.run(
            cmd, capture_output=True, encoding="utf-8", check=True
        ).stdout
    except subprocess.CalledProcessError as error:
        LOG.debug(
            "Error running shell command:\n cmd:   '%s'\n stdout: %s\n stderr: %s",
            command_str,
            error.stdout,
            error.stderr,
        )
        if raise_on_error:
            raise error
        return None


def get_subjects(outputs: dict) -> list[dict]:
    """Parse derivation outputs into in-toto subjects"""
    subjects = []
    for name, data in outputs.items():
        subject = {
            "name": name,
            "uri": data["path"],
        }
        hash = exec_cmd(
            ["nix-store", "-q", "--hash", data["path"]],
            raise_on_error=False,
        )
        if hash is None:
            LOG.warning(
                f'flake output "{name}" was not found in the nix store, assuming it was not built'
            )
        else:
            hash_type, hash_value = hash.strip().split(":")
            subject["digest"] = {hash_type: hash_value}
            subjects.append(subject)

    return subjects


def get_dependencies(drv_path: str) -> list[dict]:
    """Get dependencies of derivation and parse them into ResourceDescriptors"""
    deps_drv = exec_cmd(["nix-store", "-q", "--references", drv_path]).split()
    dependencies = []
    for drv in deps_drv:
        hash = exec_cmd(["nix-store", "-q", "--hash", drv]).strip()
        hash_type, hash_value = hash.split(":")

        dependency_json = {
            "uri": drv,
            "digest": {hash_type: hash_value},
        }

        annotations = {}

        if drv.endswith(".drv"):
            dep_json = json.loads(exec_cmd(["nix", "derivation", "show", drv]))
            env = dep_json[drv]["env"]
            dependency_json["name"] = dep_json[drv]["name"]

            version = env.get("version")
            if version:
                annotations["version"] = version

        if annotations:
            dependency_json["annotations"] = annotations

        dependencies.append(dependency_json)

    return dependencies


def timestamp(unix_time: int | str | None) -> str | None:
    """Turn unix timestamp into RFC 3339 format"""
    if unix_time is None:
        return None

    return (
        datetime.fromtimestamp(
            int(unix_time),
            tz=timezone.utc,
        ).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-4]
        + "Z"
    )


def provenance(flakeref: str) -> dict:
    """Create the provenance file"""
    flake_path, flake_target = flakeref.split("#", 1)
    flake_metadata = json.loads(
        exec_cmd(["nix", "flake", "metadata", "--json", flake_path])
    )
    drv_json = json.loads(exec_cmd(["nix", "derivation", "show", flakeref]))
    drv_path = next(iter(drv_json))
    drv_json = drv_json[drv_path]

    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": get_subjects(drv_json["outputs"]),
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": os.environ.get("PROVENANCE_BUILD_TYPE"),
                "externalParameters": json.loads(
                    os.environ.get("PROVENANCE_EXTERNAL_PARAMS", "{}")
                ),
                "internalParameters": json.loads(
                    os.environ.get("PROVENANCE_INTERNAL_PARAMS", "{}")
                ),
                "resolvedDependencies": get_dependencies(drv_path),
            },
            "runDetails": {
                "builder": {
                    "id": os.environ.get("PROVENANCE_BUILDER_ID"),
                    "builderDependencies": [],
                    "version": {},
                },
                "metadata": {
                    "invocationId": os.environ.get("PROVENANCE_INVOCATION_ID"),
                    "startedOn": timestamp(
                        os.environ.get("PROVENANCE_TIMESTAMP_BEGIN"),
                    ),
                    "finishedOn": timestamp(
                        os.environ.get("PROVENANCE_TIMESTAMP_END"),
                    ),
                },
                "byproducts": [],
            },
        },
    }


def main():
    """Main function that parses the arguments"""
    parser = argparse.ArgumentParser(
        prog="nix-provenance",
        description="Get SLSA v1.0 provenance file from nix flake",
    )
    parser.add_argument("flakeref")
    args = parser.parse_args()

    schema = provenance(args.flakeref)

    out = os.environ.get("PROVENANCE_OUTPUT_FILE")
    if out:
        with open(out, "w") as f:
            f.write(json.dumps(schema, indent=2))
    else:
        print(json.dumps(schema, indent=2))


if __name__ == "__main__":
    main()
