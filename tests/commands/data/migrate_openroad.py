import json


def main():
    new = {}
    with open("tests/commands/data/openroad.json", "r") as f:
        data = json.load(f)

    new["name"] = data["plugin"]
    new["commands"] = {}
    for command, spec in data["spec"].items():
        new["commands"][command] = {
            "positionals": {
                "min": spec[""]["min"],
                "max": spec[""]["max"],
            },
            "switches": {},
        }
        del spec[""]
        for switch, switch_spec in spec.items():
            new["commands"][command]["switches"][switch] = {
                "required": switch_spec["required"],
                "value": switch_spec["value"],
                "repeated": switch_spec["repeated"],
            }
    with open("tests/commands/data/openroad.json", "w") as f:
        json.dump(new, f)


if __name__ == "__main__":
    main()
