/*
  ==============================================================================

    TanzmausSampleTool.h
    Created: 6 Jan 2017 1:39:32pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#ifndef TANZMAUSSAMPLETOOL_H_INCLUDED
#define TANZMAUSSAMPLETOOL_H_INCLUDED


//[Headers]     -- You can add your own extra header files here --
#include "../JuceLibraryCode/JuceHeader.h"
#include "DragAndDropButton.h"
#include "pBar.h"
//[/Headers]



//==============================================================================
/**
                                                                    //[Comments]
    An auto-generated component, created by the Projucer.

    Describe your class and how it works here!
                                                                    //[/Comments]
*/
class TanzmausSampleTool  : public Component,
                       public ButtonListener,
                       public ComboBoxListener,
					   private Timer
{
public:
    //==============================================================================
    TanzmausSampleTool ();
    ~TanzmausSampleTool();

    //==============================================================================
    //[UserMethods]     -- You can add your own custom methods in this section.
	void setMidiOutput(int index);
	void timerCallback() override;
    //[/UserMethods]

    void paint (Graphics& g) override;
    void resized() override;
    void buttonClicked (Button* buttonThatWasClicked) override;
    void comboBoxChanged (ComboBox* comboBoxThatHasChanged) override;



private:
    //[UserVariables]   -- You can add your own custom variables in this section.
	ScopedPointer<Test> progBar;
	ScopedPointer<DragAndDropButton> dragButton;
	//float TEST_IT;
	unsigned int BUTTON_STATE;
	double START;
	double END_TIME;
	AudioDeviceManager audioDevice;
	MidiOutput *MidiOut;
    //[/UserVariables]

    //==============================================================================
   // ScopedPointer<TextButton> dragButton;
    ScopedPointer<ComboBox> midiOutputList;
    ScopedPointer<ComboBox> sampleDestination;
    ScopedPointer<ComboBox> sampleNumber;
    ScopedPointer<Label> label;
    ScopedPointer<Label> label2;
	ScopedPointer<Label> label3;
	int sampleNo, sampleDest;
	int sampleSize;
	MidiBuffer MidiData;
	int SAMPLE_PAGE_START_ADDR;
	int IS_RUNNING;


    //==============================================================================
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TanzmausSampleTool)
};

//[EndFile] You can add extra defines here...
//[/EndFile]


#endif  // TANZMAUSSAMPLETOOL_H_INCLUDED
