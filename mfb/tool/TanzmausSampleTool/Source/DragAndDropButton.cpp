/*
  ==============================================================================

    DragAndDropButton.cpp
    Created: 16 Dec 2016 1:14:17pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#include "../JuceLibraryCode/JuceHeader.h"
#include "DragAndDropButton.h"

//==============================================================================
DragAndDropButton::DragAndDropButton()//:
//DrawableButton("test", ImageOnButtonBackground)
{
    // In your constructor, you should add any child components, and
	//FILENAME.swapWith(String("No File Selected!"));
    SetName(TRANS("No File Selected!"));
	progBar = nullptr;
	ACTIV = 1;
    // initialise any special settings that your component needs.

}



DragAndDropButton::~DragAndDropButton()
{
}

void DragAndDropButton::SetName(const String& NEW_NAME){
    
}

/*void DragAndDropButton::paintProgress (Graphics& g)
{
 

    g.fillAll (Colours::white);   // clear the background

    g.setColour (Colours::grey);
    g.drawRect (getLocalBounds(), 1);   // draw an outline around the component

    g.setColour (Colours::lightblue);
    g.setFont (14.0f);
    g.drawText ("DragAndDropButton", getLocalBounds(),
                Justification::centred, true);   // draw some placeholder text
}*/

/*void DragAndDropButton::resized()
{
    // This method is where you should set the bounds of any child
    // components that your component contains..

}*/

void DragAndDropButton::filesDropped(const StringArray &  	files, int  	x, int  	y){
	//Logger::outputDebugString("Path: " + files[0]);
	setButtonText(String("Start Transmission!"));
	File Test(files[0]);
	if (Test.exists() == true){
		if (progBar != nullptr)progBar->ChangeBarText(Test.getFileName());
	}
	FILENAME = files[0];
}

bool DragAndDropButton::isInterestedInFileDrag(const StringArray &  	files){
	if (((files[0].contains(".wav"))||(files[0].contains(".aif"))) &&( ACTIV==1))return true;
	else return false;
	
}

void DragAndDropButton::SetDropable(void){
	ACTIV = 1;
}

void DragAndDropButton::ClearDropable(void){
	ACTIV = 0;
}

String DragAndDropButton::getFileName(void){
	return FILENAME;
}

void DragAndDropButton::SetProgressBarPointer(Test *POINTER){
	progBar = POINTER;
}


