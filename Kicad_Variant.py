import tkinter as tk
from tkinter.filedialog import askopenfilename
from kiutils.schematic import Schematic
import os
import platform	

variant_string = "Variant_"
dnf_list = ("dnf", "do not fit", "nofit", "not fitted", "dnp", "do not place",
            "no stuff", "nostuff", "noload", "do not load")
short_list = ("short", "link")


class ListBoxChoice(object):
    def __init__(self, title, message, _list):
        self.value = None
        self.list = _list[:]

        self.modalPane = tk.Toplevel()

        # self.modalPane.transient(self.master)
        self.modalPane.grab_set()

        self.modalPane.bind("<Return>", self._choose)
        self.modalPane.bind("<Escape>", self._cancel)

        if title:
            self.modalPane.title(title)

        if message:
            tk.Label(self.modalPane, text=message).pack(padx=5, pady=5)

        listFrame = tk.Frame(self.modalPane)
        listFrame.pack(side=tk.TOP, padx=5, pady=5)

        scrollBar = tk.Scrollbar(listFrame)
        scrollBar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listBox = tk.Listbox(listFrame, selectmode=tk.SINGLE, width=20)
        self.listBox.pack(side=tk.LEFT, fill=tk.Y)
        scrollBar.config(command=self.listBox.yview)
        self.listBox.config(yscrollcommand=scrollBar.set)
        self.list.sort()
        for item in self.list:
            self.listBox.insert(tk.END, item)

        buttonFrame = tk.Frame(self.modalPane)
        buttonFrame.pack(side=tk.BOTTOM)

        chooseButton = tk.Button(buttonFrame, text="Choose", command=self._choose)
        chooseButton.pack(side=tk.LEFT, padx=20)

        cancelButton = tk.Button(buttonFrame, text="Cancel", command=self._cancel)
        cancelButton.pack(side=tk.RIGHT)

    def _choose(self, event=None):
        try:
            firstIndex = self.listBox.curselection()[0]
            self.value = self.list[int(firstIndex)]
        except IndexError:
            self.value = None
        self.modalPane.destroy()

    def _cancel(self, event=None):
        self.modalPane.destroy()

    def return_value(self):
        self.modalPane.wait_window(self.modalPane)
        return self.value


if __name__ == '__main__':
    # we don't want a full GUI, so keep the root window from appearing
    root = tk.Tk()
    root.overrideredirect(True)
    root.withdraw()

    # show an "Open" dialog box and return the path to the selected file
    sch_filename = askopenfilename(filetypes=[('Kicad Schematic files', '.kicad_sch')])

    schematic = Schematic().from_file(sch_filename)

    variant_list = []
    non_variant_symbol_properties = {}

    def find_property(properties, key):
        property_index = -1
        property_value = ''

        # Search first symbol for the required property
        for idx, _property in enumerate(properties):
            if key in _property.key:
                property_index = idx
                break

        if property_value != -1:
            # The required property was found
            property_value = properties[property_index].value

        return property_index, property_value


    # Walk the schematic to get the variants types
    for symbol in schematic.schematicSymbols:
        has_variants = False
        for symbol_property in symbol.properties:
            if variant_string in symbol_property.key:
                # This symbol has variant properties
                variant_type = symbol_property.key[8:]
                if variant_type not in variant_list:
                    variant_list.append(variant_type)

                if symbol_property.value != '':
                    # This symbol has a variant value
                    has_variants = True

        if has_variants is False:
            # This is a non-variant symbol
            _, component_value = find_property(symbol.properties, 'Value')
            non_variant_symbol_properties[component_value] = symbol.properties

    selected_variant = ListBoxChoice("Variant", "Please choose a schematic variant",
                                     variant_list).return_value()
    if selected_variant is None:
        print("User cancelled")
        exit(-1)

    ret_val = True

    print("Selected variant is %s" % selected_variant)
    variant_string = variant_string + selected_variant

    # Walk the schematic to replace the variant symbol values
    for symbol in schematic.schematicSymbols:
        index, variant_component_value = find_property(symbol.properties, variant_string)

        if index == -1:
            # Selected variant not found
            continue

        if variant_component_value == '':
            # No variant specified for this symbol
            continue

        # Find the symbols reference
        index, component_reference = find_property(symbol.properties, 'Reference')
        if index == -1:
            print("Can't find ""Reference"" property")
            ret_val = False
            continue

        # Find the symbols value
        index, component_value = find_property(symbol.properties, 'Value')
        if index == -1:
            print("Can't find ""Value"" property")
            ret_val = False
            continue

        if variant_component_value == component_value:
            # No replacement required
            symbol.dnp = False
            symbol.inBom = True
            continue

        # Test for 'DNF' (Do Not Fit)
        if variant_component_value.lower() in dnf_list:
            # Do not fit
            symbol.dnp = True
            symbol.inBom = False
            print("%s : Marked as DNF" % component_reference)
            continue

        # Test for 'Short'
        if variant_component_value.lower() in short_list:
            # Do not fit
            symbol.dnp = True
            symbol.inBom = False
            print("%s : Marked as Short" % component_reference)
            continue

        if variant_component_value not in non_variant_symbol_properties:
            # Variant component not found
            print("%s : Variant value not found -> %s" % (component_reference, variant_component_value))
            ret_val = False
            continue

        # Get the replacement properties
        replacement_properties = non_variant_symbol_properties[variant_component_value]

        # Replace the symbol properties with the variant properties
        symbol.dnp = False
        symbol.inBom = True

        print("%s : Replace %s with %s" % (component_reference, component_value, variant_component_value))
        new_properties = []

        # Add non-variant properties from the variant component
        for replacement_property in replacement_properties:
            if variant_string not in replacement_property.key:
                # This is a non-variant property
                new_properties.append(replacement_property)

        # Retain variant properties from the current component
        for replacement_property in symbol.properties:
            if variant_string in replacement_property.key:
                # This is a variant property
                new_properties.append(replacement_property)

        # Replace original symbol with new properties
        symbol.properties = new_properties

    if ret_val is True:
        print("Updating file")
        schematic.to_file()
    else:
        print("Errors present - File not updated")

    print("Finished")

    if platform.system() == "Windows":
        os.system("pause")
    else:
        os.system("/bin/bash -c 'read -s -n 1 -p \"Press any key to continue...\"'")
