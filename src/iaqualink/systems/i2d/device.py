from iaqualink.device import AqualinkDevice


class AquaLinkIQPump(AqualinkDevice):
    @property
    def label(self) -> str:
        return self.system.name

    @property
    def state(self) -> str:
        return self.data["runstate"]

    @property
    def name(self) -> str:
        return self.system.name

    @property
    def manufacturer(self) -> str:
        return "Jandy"

    @property
    def model(self) -> str:
        return "IQPump " + self.data["motordata"]["productid"]

    @property
    def firmware(self) -> str:
        return self.data["fwversion"]

    @property
    def productId(self) -> str:
        return self.data["motordata"]["productid"]

    @property
    def motorSpeed(self) -> int:
        return int(self.data["motordata"]["speed"])

    @property
    def motorPower(self) -> int:
        return int(self.data["motordata"]["power"])

    @property
    def motorTemperature(self) -> int:
        return int(self.data["motordata"]["temperature"])

    @property
    def horsepower(self) -> str:
        return self.data["motordata"]["horsepower"]

    @property
    def horsepowerCode(self) -> str:
        return self.data["motordata"]["horsepowerCode"]

    @property
    def freezeProtectStatus(self) -> int:
        return int(self.data["freezeprotectstatus"])

    @property
    def freezeProtectEnable(self) -> int:
        return int(self.data["freezeprotectenable"])
