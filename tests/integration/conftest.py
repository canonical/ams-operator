def pytest_addoption(parser):
    parser.addoption("--ams-snap", required=True, action="store", help="Snap resource for ams")

    parser.addoption("--constraints", default="", action="store", help="Model constraints")
