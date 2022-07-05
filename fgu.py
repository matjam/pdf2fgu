import xml.etree.ElementTree as ET

def echo(fn):
    from itertools import chain
    def wrapped(*v, **k):
        name = fn.__name__
        #print("%s(%s)" % (name, ", ".join(map(repr, chain(v, k.values())))))
        return fn(*v, **k)
    return wrapped



class Story:
    currentID = 1

    def __init__(self, name, *, locked=False):
        self.buildingFrame = False
        self.buildingParagraph = False
        self.buildingTable = False
        self.buildingTableRow = False
        self.buildingTableData = False
        self.buildingList = False
        self.buildingListEntry = False
        self.bold = False
        self.italic = False

        self.id = Story.currentID
        Story.currentID = Story.currentID + 1
        self.name = name
        self.builder = ET.TreeBuilder()
        self.builder.start(f"id-{self.id:05d}", {})

        if locked:
            self.builder.start("locked", {"type": "number"})
            self.builder.data('1')
            self.builder.end("locked")

        self.builder.start("name", {"type": "string"})
        self.builder.data(self.name)
        self.builder.end("name")
        self.builder.start("text", {"type": "formattedtext"})
    
    @echo
    def close(self):
        self.builder.end("text")
        self.builder.end(f"id-{self.id:05d}")
        return self.builder.close()

    @echo
    def startFrame(self):
        if self.buildingFrame:
            raise Exception("frame already started for this story. Did you forget to end the previous frame?")
        self.buildingFrame = True
        self.builder.start("frame", {})
    
    @echo
    def endFrame(self):
        if not self.buildingFrame:
            raise Exception("frame not started for this story. Did you forget to start a frame?")
        self.buildingFrame = False
        self.builder.end("frame")

    @echo
    def addText(self, text, *, bold=False, italic=False):
        if bold != self.bold or italic != self.italic:
            if self.italic:
                self.italic = False
                self.builder.end('i')
            if self.bold:
                self.bold = False
                self.builder.end('b')

            if bold:
                self.builder.start('b', {})
                self.bold = True

            if italic:
                self.builder.start('i', {})
                self.italic = True

        self.builder.data(text)
    
    @echo
    def addHeading(self, text):
        self.builder.start('h', {})
        self.builder.data(text)
        self.builder.end('h')

    @echo
    def startParagraph(self):
        if self.buildingParagraph:
            raise Exception("paragraph already started for this story. Did you forget to end the previous paragraph?")
        self.buildingParagraph = True
        self.builder.start("p", {})
    
    @echo
    def endParagraph(self):
        if self.italic:
            self.italic = False
            self.builder.end('i')
        
        if self.bold:
            self.bold = False
            self.builder.end('b')

        if not self.buildingParagraph:
            raise Exception("paragraph not started for this story. Did you forget to start a paragraph?")
        self.buildingParagraph = False
        return self.builder.end("p")

    @echo
    def startBold(self):
        self.builder.start("b", {})
    
    @echo
    def endBold(self):
        self.builder.end("b")

    @echo
    def startItalic(self):
        self.builder.start("i", {})
    
    @echo
    def endItalic(self):
        self.builder.end("i")

    @echo
    def startTable(self):
        if self.buildingTable:
            raise Exception("already building a table")
        self.buildingTable = True
        self.builder.start("table", {})

    @echo
    def endTable(self):
        if not self.buildingTable:
            raise Exception("not building a table")
        self.buildingTable = False
        self.builder.end("table")
    
    @echo
    def startTableRow(self):
        if self.buildingTableRow:
            raise Exception("already building a tableRow")
        self.buildingTableRow = True
        self.builder.start("tr", {})

    @echo
    def endTableRow(self):
        if not self.buildingTableRow:
            raise Exception("not building a tableRow")
        self.buildingTableRow = False
        self.builder.end("tr")
    
    @echo
    def startTableData(self):
        if self.buildingTableData:
            raise Exception("already building a tableData")
        self.buildingTableData = True
        self.builder.start("td", {})

    @echo
    def endTableData(self):
        if not self.buildingTableData:
            raise Exception("not building a tableData")
        self.buildingTableData = False
        self.builder.end("td")

    @echo
    def startList(self):
        if self.buildingList:
            raise Exception("already building a list")
        self.buildingList = True
        self.builder.start("list", {})

    @echo
    def endList(self):
        if not self.buildingList:
            raise Exception("not building a list")
        self.buildingList = False
        self.builder.end("list")

    @echo
    def startListEntry(self):
        if self.buildingListEntry:
            raise Exception("already building a list entry")
        self.buildingListEntry = True
        self.builder.start("li", {})

    @echo    
    def endListEntry(self):
        if not self.buildingListEntry:
            raise Exception("not building a list entry")
        self.buildingListEntry = False
        self.builder.end("li")

    @echo
    def addBreak(self):
        self.builder.start("br", {})
        self.builder.end("br")    

    @echo
    def addPartyStrengthTable(self):
        partyStrengthTable = [
            ["3-4 characters, APL less than", "Very weak"],
            ["3-4 characters, APL equivalent", "Weak"],
            ["3-4 characters, APL greater than", "Average"],
            ["5 characters, APL less than", "Weak"],
            ["5 characters, APL equivalent", "Average"],
            ["5 characters, APL greater than", "Strong"],
            ["6-7 characters, APL less than", "Average"],
            ["6-7 characters, APL equivalent", "Strong"],
            ["6-7 characters, APL greater than", "Very strong"],
        ]

        self.startTable()
        self.startTableRow()
        self.startTableData()
        self.builder.start("b", {})
        self.builder.data("Party Composition")
        self.builder.end("b")
        self.endTableData()
        self.startTableData()
        self.builder.start("b", {})
        self.builder.data("Party Strength")
        self.builder.end("b")
        self.endTableData()
        self.endTableRow()

        for row in partyStrengthTable:
                self.startTableRow()
                self.startTableData()
                self.addText(row[0])
                self.endTableData()
                self.startTableData()
                self.addText(row[1])
                self.endTableData()
                self.endTableRow()

        self.endTable()
    