/*
  ==============================================================================

    TanzmausSampleTool.cpp
    Created: 6 Jan 2017 1:39:32pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#include "TanzmausSampleTool.h"
//[Headers] You can add your own extra header files here...
//[/Headers]


#include "crc7.h"


//[MiscUserDefs] You can add your own user definitions and misc code here...
//[/MiscUserDefs]

//==============================================================================
TanzmausSampleTool::TanzmausSampleTool ()
{
    //[Constructor_pre] You can add your own custom stuff here..
	addAndMakeVisible(dragButton = new DragAndDropButton());
	dragButton->setButtonText(TRANS("Drop Sample here!"));
	dragButton->addListener(this);

	addAndMakeVisible(progBar = new Test);
	dragButton->SetProgressBarPointer(progBar);
	//TEST_IT = 0;
	BUTTON_STATE = 0;

	addAndMakeVisible(label3 = new Label("new label",
		TRANS("Sample Length: 0.5s")));
	label3->setFont(Font(15.00f, Font::plain));
	label3->setJustificationType(Justification::centredLeft);
	label3->setEditable(false, false, false);
	label3->setColour(TextEditor::textColourId, Colours::black);
	label3->setColour(TextEditor::backgroundColourId, Colour(0x00000000));
    //[/Constructor_pre]

    /*addAndMakeVisible (dragButton = new TextButton ("new button"));
    dragButton->setButtonText (TRANS("Drop Sample here!"));
    dragButton->addListener (this);*/

    addAndMakeVisible (midiOutputList = new ComboBox ("new combo box"));
    midiOutputList->setEditableText (false);
    midiOutputList->setJustificationType (Justification::centredLeft);
    midiOutputList->setTextWhenNothingSelected (TRANS("please select your midi interface"));
    midiOutputList->setTextWhenNoChoicesAvailable (TRANS("(no choices)"));
	const StringArray midiOutputs(MidiOutput::getDevices());
	midiOutputList->addItemList(midiOutputs, 1);
    midiOutputList->addListener (this);

    addAndMakeVisible (sampleDestination = new ComboBox ("new combo box"));
    sampleDestination->setEditableText (false);
    sampleDestination->setJustificationType (Justification::centredLeft);
    sampleDestination->setTextWhenNothingSelected (TRANS("Please Select!"));
    sampleDestination->setTextWhenNoChoicesAvailable (TRANS("(no choices)"));
    sampleDestination->addItem (TRANS("Sample 1"), 1);
    sampleDestination->addItem (TRANS("Sample 2"), 2);
    sampleDestination->addListener (this);
	sampleDestination->setSelectedId(1, sendNotification);

    addAndMakeVisible (sampleNumber = new ComboBox ("new combo box"));
    sampleNumber->setEditableText (false);
    sampleNumber->setJustificationType (Justification::centredLeft);
    sampleNumber->setTextWhenNothingSelected (String());
    sampleNumber->setTextWhenNoChoicesAvailable (TRANS("(no choices)"));
    sampleNumber->addItem (TRANS("1"), 1);
    sampleNumber->addItem (TRANS("2"), 2);
    sampleNumber->addItem (TRANS("3"), 3);
    sampleNumber->addItem (TRANS("4"), 4);
    sampleNumber->addItem (TRANS("5"), 5);
    sampleNumber->addItem (TRANS("6"), 6);
    sampleNumber->addItem (TRANS("7"), 7);
    sampleNumber->addItem (TRANS("8"), 8);
    sampleNumber->addItem (TRANS("9"), 9);
    sampleNumber->addItem (TRANS("10"), 10);
    sampleNumber->addItem (TRANS("11"), 11);
    sampleNumber->addItem (TRANS("12"), 12);
    sampleNumber->addItem (TRANS("13"), 13);
    sampleNumber->addItem (TRANS("14"), 14);
    sampleNumber->addItem (TRANS("15"), 15);
    sampleNumber->addItem (TRANS("16"), 16);
    sampleNumber->addListener (this);
	sampleNumber->setSelectedId(1, sendNotification);

    addAndMakeVisible (label = new Label ("new label",
                                          TRANS("Sample Number")));
    label->setFont (Font (15.00f, Font::plain));
    label->setJustificationType (Justification::centredLeft);
    label->setEditable (false, false, false);
    label->setColour (TextEditor::textColourId, Colours::black);
    label->setColour (TextEditor::backgroundColourId, Colour (0x00000000));

    addAndMakeVisible (label2 = new Label ("new label",
                                           TRANS("Sample Destination")));
    label2->setFont (Font (15.00f, Font::plain));
    label2->setJustificationType (Justification::centredLeft);
    label2->setEditable (false, false, false);
    label2->setColour (TextEditor::textColourId, Colours::black);
    label2->setColour (TextEditor::backgroundColourId, Colour (0x00000000));


    //[UserPreSize]
    //[/UserPreSize]

    setSize (218, 250);


    //[Constructor] You can add your own custom stuff here..
	MidiOut = nullptr;
	IS_RUNNING = 0;
    //[/Constructor]
}

TanzmausSampleTool::~TanzmausSampleTool()
{
    //[Destructor_pre]. You can add your own custom destruction code here..
    //[/Destructor_pre]

    dragButton = nullptr;
    midiOutputList = nullptr;
    sampleDestination = nullptr;
    sampleNumber = nullptr;
    label = nullptr;
    label2 = nullptr;


    //[Destructor]. You can add your own custom destruction code here..
	progBar = nullptr;
	if (MidiOut != nullptr){
		MidiOut->stopBackgroundThread();

		delete MidiOut;
	}
    //[/Destructor]
}

//==============================================================================
void TanzmausSampleTool::paint (Graphics& g)
{
    //[UserPrePaint] Add your own custom painting code here..
    //[/UserPrePaint]

    g.fillAll (Colours::white);

    //[UserPaint] Add your own custom painting code here..
    //[/UserPaint]
}

void TanzmausSampleTool::resized()
{
    //[UserPreResize] Add your own custom resize code here..
    //[/UserPreResize]

    
    midiOutputList->setBounds (8, 8, 200, 24);
    sampleDestination->setBounds (8, 64, 200, 24);
    sampleNumber->setBounds (8, 120, 64, 24);
	dragButton->setBounds(8, 152, 200, 56);
    label->setBounds (8, 96, 150, 24);
    label2->setBounds (8, 40, 150, 24);
    //[UserResized] Add your own custom resize handling here..
	progBar->setBounds(8, 220, 200, 20);
	label3->setBounds(70, 120, 200, 24);
    //[/UserResized]
}

void TanzmausSampleTool::buttonClicked (Button* buttonThatWasClicked)
{
    //[UserbuttonClicked_Pre]
	if (buttonThatWasClicked == dragButton)
	{
		//[UserButtonCode_textButton] -- add your button handler code here..
		if ((dragButton->getFileName() != "No File Selected!") && (MidiOut != nullptr) && (IS_RUNNING==0)) {
			File SampleDataFile(dragButton->getFileName());
			dragButton->setButtonText(SampleDataFile.getFileName());


			if ( SampleDataFile.exists()) {

				AudioFormatManager formatManager;

				ScopedPointer<AudioFormatReader> reader;// = formatManager.createReaderFor(file);
				formatManager.registerBasicFormats();



				unsigned short AUDIO_DATA[88176];
				Crc7 SysExData;
				int i;
				int SAMPLE_POS = 0;
				int WAITING_TIME_SHORT = 1056;//ca.20ms @48000 SR - 48=1ms
				int WAITING_TIME_LONG = 1056;
				int WAITING_TIME_FIRST_PACKAGE = 1056;

				reader = formatManager.createReaderFor(SampleDataFile);
				if (reader != 0) {
					juce::AudioSampleBuffer buffer1(1, reader->lengthInSamples);

					reader->read(&buffer1, 0, reader->lengthInSamples, 0, true, false);

					for (i = 0; i < sampleSize; i++) {
						if (i < reader->lengthInSamples)AUDIO_DATA[i] = ((unsigned short)((buffer1.getSample(0, i) * 32768.0) + 32768.0) >> 4);// >> (16 - (unsigned char)BIT_DEPH));
						else AUDIO_DATA[i] = 0;
					}
					//buffer1.readFromAudioReader(reader, 0, reader->lengthInSamples, 0, true, true);
					//float* firstChannelSamples = buffer1.getSampleData(0, 0);
				}

				SysExData.AddStartMessage(sampleNo);

				for (i = 0; i < sampleSize; i += 264) {
					SysExData.AddPage(&AUDIO_DATA[(i / 264) * 264], SAMPLE_PAGE_START_ADDR + (i / 264));
				}

				SysExData.AddStopMessage();


				MidiData.clear();
				MidiOut->clearAllPendingMessages();
				for (i = 0; i < SysExData.GetSize(); i++) {//NO_OF_MESSAGES	//SysExData.GetSize()
					MidiData.addEvent(SysExData.GetMessage(i), SAMPLE_POS);

					SAMPLE_POS += WAITING_TIME_FIRST_PACKAGE;


				}
				if (&MidiData != nullptr)MidiOut->sendBlockOfMessages(MidiData, Time::getMillisecondCounter() + 1.0, 48000);

				//
				//TEST_IT += 0.1;
				//progBar->progress(TEST_IT);
				START = Time::getMillisecondCounter();
				END_TIME = SysExData.GetSize() * 23;
				startTimer(100);
				IS_RUNNING = 1;
				dragButton->ClearDropable();
				
			}
		}
		//[/UserButtonCode_textButton]
	}
    //[/UserbuttonClicked_Pre]



    //[UserbuttonClicked_Post]
    //[/UserbuttonClicked_Post]
}

void TanzmausSampleTool::comboBoxChanged (ComboBox* comboBoxThatHasChanged)
{
    //[UsercomboBoxChanged_Pre]
    //[/UsercomboBoxChanged_Pre]

    if (comboBoxThatHasChanged == midiOutputList)
    {
        //[UserComboBoxCode_midiOutputList] -- add your combo box handling code here..
		setMidiOutput(midiOutputList->getSelectedItemIndex());
        //[/UserComboBoxCode_midiOutputList]
    }
    else if (comboBoxThatHasChanged == sampleDestination)
    {
        //[UserComboBoxCode_sampleDestination] -- add your combo box handling code here..
		sampleDest = sampleDestination->getSelectedItemIndex();
        //[/UserComboBoxCode_sampleDestination]
    }
    else if (comboBoxThatHasChanged == sampleNumber)
    {
        //[UserComboBoxCode_sampleNumber] -- add your combo box handling code here..
		sampleNo = sampleNumber->getSelectedItemIndex();

		if (sampleNo < 4){	//0...3 4...7
			sampleSize = 22000;
			SAMPLE_PAGE_START_ADDR = (((sampleDest*4)+sampleNo) * 91);
			label3->setText(TRANS("Sample Length: 0.5s"), dontSendNotification);
			
		}
		else{
			if (sampleNo < 12){//8...15 16...23
				sampleSize = 44000;
				SAMPLE_PAGE_START_ADDR = 728 + (((sampleDest * 8) + (sampleNo-4)) * 182);
				label3->setText(TRANS("Sample Length: 1s"), dontSendNotification);
			}
			else {//24...27 28...31
				sampleSize = 88000;
				SAMPLE_PAGE_START_ADDR = 3640 +(((sampleDest * 4) + (sampleNo-12)) * 364);
				label3->setText(TRANS("Sample Length: 2s"), dontSendNotification);
			}
		}
        //[/UserComboBoxCode_sampleNumber]
    }

    //[UsercomboBoxChanged_Post]
    //[/UsercomboBoxChanged_Post]
}

/*
const unsigned int SAMPLE_LENGTH[4]={22000,44000,44000,88000};	//@44100 SR*/

//[MiscUserCode] You can add your own definitions of your custom methods or any other code here...
void TanzmausSampleTool::timerCallback(){
	double TEST_IT = ((Time::getMillisecondCounter() - START) / END_TIME);
	if (TEST_IT<1.0)progBar->progress(TEST_IT);
	else {
		stopTimer();
		progBar->ChangeBarText(String("Done"));
		IS_RUNNING = 0;
		dragButton->SetDropable();
		dragButton->setButtonText(TRANS("Drop Sample here!"));


	}
}

void TanzmausSampleTool::setMidiOutput(int index)
{
	if (MidiOut != nullptr){
		MidiOut->stopBackgroundThread();

		delete MidiOut;
	}
	MidiOut=MidiOutput::openDevice(index);

	MidiOut->startBackgroundThread();

}
//[/MiscUserCode]