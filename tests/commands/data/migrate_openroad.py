import json


def main():
    new = {}
    with open("tests/commands/data/openroad.json", "r") as f:
        data = json.load(f)

    new["name"] = data["name"]
    new["commands"] = {}
    for command, spec in data["commands"].items():
        new["commands"][command] = {}

        min_ = spec["positionals"]["min"]
        max_ = spec["positionals"]["max"]
        positionals = []
        for i in range(min_):
            positionals.append({
                "name": f"arg{i + 1}",
                "required": True,
                "value": {"type": "any"},
            })

        if max_ is None:
            positionals.append({
                "name": "remaining",
                "required": False,
                "value": {"type": "variadic"},
            })
        else:
            for i in range(min_, max_):
                positionals.append({
                    "name": f"arg{i + 1}",
                    "required": False,
                    "value": {"type": "any"},
                })

        if positionals:
            new["commands"][command]["positionals"] = positionals

        switches = {}
        for switch, switch_spec in spec["switches"].items():
            switches[switch] = {
                "required": switch_spec["required"],
                "value": {"type": "any"} if switch_spec["value"] else None,
                "repeated": switch_spec["repeated"],
            }

        if switches:
            new["commands"][command]["switches"] = switches

    with open("tests/commands/data/openroad.json", "w") as f:
        json.dump(new, f)


if __name__ == "__main__":
    main()
