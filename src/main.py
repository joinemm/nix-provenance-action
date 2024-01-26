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
            ["nix-store", "--query", "--hash", data["path"]],
            raise_on_error=False,
        )
        if hash is None:
            LOG.warning(
                f'Derivation output "{name}" was not found in the nix store, assuming it was not built'
            )
        else:
            hash_type, hash_value = hash.strip().split(":")
            subject["digest"] = {hash_type: hash_value}
            subjects.append(subject)

    return subjects


def get_dependencies(drv_path: str, recursive: bool = False) -> list[dict]:
    """Get dependencies of derivation and parse them into ResourceDescriptors"""
    depth = "--requisites" if recursive else "--references"
    deps_drv = exec_cmd(["nix-store", "--query", depth, drv_path]).split()

    dependencies = []
    for drv in deps_drv:
        hash = exec_cmd(["nix-store", "--query", "--hash", drv]).strip()
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


def get_external_parameters(drv_path: str) -> dict:
    """Get externalParameters from env variable and add derivation"""
    params = json.loads(os.environ.get("PROVENANCE_EXTERNAL_PARAMS", "{}"))

    # add derivation path always to params
    params["derivation"] = drv_path

    # return only params with non-empty values
    return {k: v for k, v in params.items() if v}


def get_internal_parameters() -> dict:
    """Get internalParameters from env variable"""
    return json.loads(os.environ.get("PROVENANCE_INTERNAL_PARAMS", "{}"))


def timestamp(unix_time: int | str | None) -> str | None:
    """Turn unix timestamp into RFC 3339 format"""
    if unix_time is None:
        return None

    return (
        datetime.fromtimestamp(
            int(unix_time),
            tz=timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4]
        + "Z"
    )


def provenance(target: str, recursive: bool = False) -> dict:
    """Create the provenance file"""
    drv_json = json.loads(exec_cmd(["nix", "derivation", "show", target]))
    drv_path = next(iter(drv_json))
    drv_json = drv_json[drv_path]

    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": get_subjects(drv_json["outputs"]),
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": os.environ.get("PROVENANCE_BUILD_TYPE"),
                "externalParameters": get_external_parameters(drv_path),
                "internalParameters": get_internal_parameters(),
                "resolvedDependencies": get_dependencies(drv_path, recursive),
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
    """Main function that parses the arguments and writes provenance file"""
    parser = argparse.ArgumentParser(
        prog="nix-provenance",
        description="Get SLSA v1.0 provenance file from nix flake or derivation",
    )
    parser.add_argument(
        "target",
        help="Flake reference or derivation path",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Resolve every dependency recursively",
    )
    parser.add_argument(
        "--out",
        help="Path to file where provenance should be saved",
        default=os.environ.get("PROVENANCE_OUTPUT_FILE"),
    )
    args = parser.parse_args()

    # generate provenance
    schema = provenance(args.target, args.recursive)

    if args.out:
        with open(args.out, "w") as f:
            f.write(json.dumps(schema, indent=2))
    else:
        print(json.dumps(schema, indent=2))


if __name__ == "__main__":
    main()
