/*
  ==============================================================================

    Test.cpp
    Created: 16 Dec 2016 3:47:38pm
    Author:  Sebastian Preller

  ==============================================================================
*/

#include "../JuceLibraryCode/JuceHeader.h"
#include "pBar.h"

//==============================================================================
Test::Test()
{
    // In your constructor, you should add any child components, and
    // initialise any special settings that your component needs.
	progValue = 0;
	//BAR_TEXT.swapWith("no file selected!");
    ChangeBarText(TRANS("no file selected!"));

}

Test::~Test()
{
}

void Test::paint (Graphics& g)
{
    /* This demo code just fills the component's background and
       draws some placeholder text to get you started.

       You should replace everything in this method with your own
       drawing code..
    */

    g.fillAll (Colours::white);   // clear the background

    g.setColour (Colours::darkred);
    g.drawRect (getLocalBounds(), 1);   // draw an outline around the component

	
	
	g.fillRect(Rectangle<float>(0, 0, getLocalBounds().getWidth()*progValue, getLocalBounds().getHeight()));

	g.setColour(Colours::grey);
    g.setFont (14.0f);
	g.drawText(BAR_TEXT, getLocalBounds(),
                Justification::centred, true);   // draw some placeholder text
}

void Test::resized()
{
    // This method is where you should set the bounds of any child
    // components that your component contains..

}

void Test::progress(float prog){
	progValue = prog;
	repaint();
}

void Test::ChangeBarText(String TEXT){
	BAR_TEXT.swapWith(TEXT);
	repaint();
}

